#!/usr/bin/env python3
"""Sustained-load soak test for the Jetson + D435i.

Streams depth, colour and (when exposed) IMU for a fixed time while aligning
every depth frame to colour on the CPU, and logs one JSON line every interval:
per-stream frames, frame-number gaps, longest interval, frames the processing
thread could not keep up with, processing time, temperatures and clock speeds.
`tegrastats` runs alongside for power, CPU/GPU load and RAM. A final JSON
summary is printed at the end.

Run on the Jetson inside the venv that has pyrealsense2 (no recording):

    ~/ugv-nav/.venv/bin/python tools/jetson_soak.py --minutes 20 \
        --out ~/ugv-data/soak/<session>

Writes <out>.jsonl (intervals), <out>.tegrastats.log and <out>.summary.json.
"""

from __future__ import annotations

import argparse
import json
import queue
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyrealsense2 as rs
from realsense_check import imu_available, sdk_build

THERMAL = Path("/sys/devices/virtual/thermal")
CPU_FREQ = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")


@dataclass
class StreamWindow:
    """Per-stream counters for one logging interval."""

    frames: int = 0
    gaps: int = 0
    resets: int = 0
    max_interval_ms: float = 0.0
    last_number: int | None = None
    last_ts: float | None = None

    def add(self, number: int, ts: float) -> None:
        if self.last_number is not None:
            step = number - self.last_number
            if step > 1:
                self.gaps += step - 1
            elif step <= 0:
                self.resets += 1
        if self.last_ts is not None:
            self.max_interval_ms = max(self.max_interval_ms, ts - self.last_ts)
        self.frames += 1
        self.last_number, self.last_ts = number, ts

    def flush(self) -> dict[str, Any]:
        out = {"frames": self.frames, "gaps": self.gaps, "resets": self.resets,
               "max_interval_ms": round(self.max_interval_ms, 1)}
        self.frames = self.gaps = self.resets = 0
        self.max_interval_ms = 0.0
        return out  # last_number/last_ts carry over so gaps across windows count


@dataclass
class Totals:
    queue_drops: int = 0
    stale: int = 0
    process_ms: list[float] = field(default_factory=list)
    processed: int = 0


def read_temps() -> dict[str, float]:
    temps: dict[str, float] = {}
    for zone in sorted(THERMAL.glob("thermal_zone*")):
        try:
            temps[(zone / "type").read_text().strip()] = int((zone / "temp").read_text()) / 1000.0
        except (OSError, ValueError):
            continue  # some zones report no data
    return temps


def read_clocks() -> dict[str, float]:
    clocks: dict[str, float] = {}
    try:
        clocks["cpu0_mhz"] = int(CPU_FREQ.read_text()) / 1000.0
    except (OSError, ValueError):
        pass
    for dev in Path("/sys/class/devfreq").glob("*"):
        if "gpu" in dev.name or "ga10b" in dev.name:
            try:
                clocks["gpu_mhz"] = int((dev / "cur_freq").read_text()) / 1e6
            except (OSError, ValueError):
                pass
    return clocks


def percentiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    arr = np.asarray(values)
    return {"median": round(float(np.median(arr)), 2), "p95": round(float(np.percentile(arr, 95)), 2),
            "max": round(float(arr.max()), 2)}


def soak(minutes: float, interval_s: float, out: Path) -> dict[str, Any]:
    """Run the soak and return the summary; interval lines go to <out>.jsonl."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with_imu = imu_available()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 848, 480, rs.format.rgb8, 30)
    if with_imu:
        config.enable_stream(rs.stream.accel)
        config.enable_stream(rs.stream.gyro)

    windows: dict[str, StreamWindow] = {}
    totals = Totals()
    framesets: queue.Queue[rs.composite_frame] = queue.Queue(maxsize=30)
    start_wall_ms = time.time() * 1000.0 - 50.0

    def count(f: rs.frame) -> None:
        ts = f.get_timestamp()
        if f.is_motion_frame() and f.get_frame_timestamp_domain() == rs.timestamp_domain.global_time \
                and not start_wall_ms <= ts <= time.time() * 1000.0 + 1000.0:
            totals.stale += 1  # start-up IMU samples stamped before the session or far ahead
            return
        windows.setdefault(f.get_profile().stream_name(), StreamWindow()).add(f.get_frame_number(), ts)

    def on_frame(frame: rs.frame) -> None:
        if not frame.is_frameset():
            count(frame)
            return
        fs = frame.as_frameset()
        for i in range(fs.size()):
            count(fs[i])
        if fs.get_depth_frame() and fs.get_color_frame():  # sets may hold only IMU samples
            fs.keep()
            try:
                framesets.put_nowait(fs)
            except queue.Full:
                totals.queue_drops += 1  # processing could not keep up

    tegra_log = out.with_suffix(".tegrastats.log")
    tegra = subprocess.Popen(["tegrastats", "--interval", "1000", "--logfile", str(tegra_log)])
    align = rs.align(rs.stream.color)
    pipeline = rs.pipeline()
    pipeline.start(config, on_frame)
    lines: list[dict[str, Any]] = []
    t0 = next_log = time.monotonic()
    try:
        with out.with_suffix(".jsonl").open("w") as log:
            while time.monotonic() - t0 < minutes * 60.0:
                try:
                    fs = framesets.get(timeout=0.5)
                except queue.Empty:
                    fs = None
                if fs is not None:
                    began = time.perf_counter()
                    aligned = align.process(fs)
                    depth = np.asanyarray(aligned.get_depth_frame().get_data())
                    _ = np.count_nonzero(depth) / depth.size  # representative per-frame work
                    totals.process_ms.append((time.perf_counter() - began) * 1000.0)
                    totals.processed += 1
                if time.monotonic() >= next_log + interval_s:
                    next_log += interval_s
                    line = {
                        "t_s": round(time.monotonic() - t0, 1),
                        "streams": {name: w.flush() for name, w in sorted(windows.items())},
                        "processed": totals.processed,
                        "process_ms": percentiles(totals.process_ms),
                        "queue_drops_total": totals.queue_drops,
                        "stale_total": totals.stale,
                        "temps_c": read_temps(),
                        "clocks": read_clocks(),
                    }
                    totals.processed, totals.process_ms = 0, []
                    log.write(json.dumps(line) + "\n")
                    log.flush()
                    lines.append(line)
    finally:
        pipeline.stop()
        tegra.terminate()
        tegra.wait(timeout=10)

    return summarize(lines, interval_s, sdk_build(), with_imu, out)


def summarize(lines: list[dict[str, Any]], interval_s: float, sdk: dict[str, str],
              with_imu: bool, out: Path) -> dict[str, Any]:
    """Reduce interval lines to totals and first/last/max values (pure)."""
    steady = lines[1:]  # the first interval contains start-up transients
    streams: dict[str, dict[str, Any]] = {}
    for line in steady:
        for name, s in line["streams"].items():
            agg = streams.setdefault(name, {"frames": 0, "gaps": 0, "resets": 0, "max_interval_ms": 0.0})
            agg["frames"] += s["frames"]
            agg["gaps"] += s["gaps"]
            agg["resets"] += s["resets"]
            agg["max_interval_ms"] = max(agg["max_interval_ms"], s["max_interval_ms"])
    seconds = interval_s * len(steady)
    for agg in streams.values():
        agg["mean_rate_hz"] = round(agg["frames"] / seconds, 2) if seconds else None
    temp_keys = sorted({k for line in lines for k in line["temps_c"]})
    return {
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "versions": sdk,
        "imu_exposed": with_imu,
        "intervals": len(lines),
        "steady_seconds": seconds,
        "streams_steady": streams,
        "processed_per_s": [round(line["processed"] / interval_s, 1) for line in lines],
        "process_ms_p95_max": max((line["process_ms"]["p95"] for line in lines if line["process_ms"]), default=None),
        "queue_drops_total": lines[-1]["queue_drops_total"] if lines else None,
        "stale_total": lines[-1]["stale_total"] if lines else None,
        "temps_first_last_max": {
            k: [lines[0]["temps_c"].get(k), lines[-1]["temps_c"].get(k),
                max(line["temps_c"].get(k, float("-inf")) for line in lines)] for k in temp_keys
        } if lines else {},
        "clocks_min": {
            k: min(line["clocks"][k] for line in lines if k in line["clocks"])
            for k in sorted({k for line in lines for k in line["clocks"]})
        },
        "files": {"intervals": out.with_suffix(".jsonl").name, "tegrastats": out.with_suffix(".tegrastats.log").name},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--minutes", type=float, default=20.0)
    parser.add_argument("--interval", type=float, default=10.0, help="seconds per log line")
    parser.add_argument("--out", type=Path, required=True, help="output path prefix (no extension)")
    args = parser.parse_args()
    out = args.out.expanduser()
    if out.with_suffix(".jsonl").exists():
        parser.error(f"{out}.jsonl already exists; use a new session name")
    summary = soak(args.minutes, args.interval, out)
    out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
