#!/usr/bin/env python3
"""Stationary RealSense stream check for the D435i.

Streams RGB, depth and (when exposed) accel and gyro for a fixed time,
optionally records them (librealsense >= 2.58 writes ROS 2 .db3 files) and
reads the file back per sensor. Prints a JSON summary: device/firmware, stream
profiles, calibration, per-stream rates, frame-number gaps and counter resets,
timestamp behaviour, invalid depth, IMU sanity, which device nodes the SDK
opened (backend evidence), and frames recorded versus delivered.

Run on the Jetson inside the venv that has pyrealsense2, keeping recordings
outside Git:

    ~/ugv-nav/.venv/bin/python tools/realsense_check.py --seconds 10 \
        --record ~/ugv-data/recordings/<session>.db3

Notes on the numbers:
- Frames are identified by (frame number, timestamp): the D435i depth stream
  restarts its frame counter shortly after start-up, so numbers alone repeat.
- Samples whose global timestamp precedes the session start are counted as
  `stale_at_start`, and samples stamped more than 1 s after their own arrival as
  `future_stamped`; both are left out of the statistics.
- `receive_minus_timestamp_ms` is host receive time minus the SDK's global
  timestamp. It includes the SDK's device-to-host clock-mapping error (it can
  be negative), so it is not a latency measurement.

The summary deliberately omits device serial numbers and the home directory.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyrealsense2 as rs


@dataclass
class StreamLog:
    """Raw per-stream observations collected in the frame callback."""

    timestamps_ms: list[float] = field(default_factory=list)  # kept frames only
    frame_numbers: list[int] = field(default_factory=list)  # kept frames only
    seen_frames: set[tuple[int, float]] = field(default_factory=set)
    received: int = 0  # distinct frames delivered to the callback, stale ones included
    duplicate_deliveries: int = 0  # same (number, timestamp) delivered again
    stale_at_start: int = 0  # global timestamp before the session started
    future_stamped: int = 0  # global timestamp > 1 s after the sample's arrival
    first_arrival_s: float | None = None  # host monotonic, relative to start
    domains: set[str] = field(default_factory=set)
    receive_minus_timestamp_ms: list[float] = field(default_factory=list)  # global time only
    has_sensor_timestamp: bool = False
    invalid_depth_fraction: list[float] = field(default_factory=list)
    motion_xyz: list[tuple[float, float, float]] = field(default_factory=list)


def _percentiles(values: np.ndarray) -> dict[str, float]:
    return {
        "min": round(float(np.min(values)), 3),
        "median": round(float(np.median(values)), 3),
        "p95": round(float(np.percentile(values, 95)), 3),
        "max": round(float(np.max(values)), 3),
    }


def summarize(log: StreamLog, nominal_fps: float) -> dict[str, Any]:
    """Compute rate, gap and quality statistics for one stream (pure)."""
    n = len(log.timestamps_ms)
    global_only = bool(log.domains) and log.domains <= {"global_time"}
    out: dict[str, Any] = {
        "frames_kept": n,
        "frames_received": log.received,
        "nominal_fps": nominal_fps,
        "duplicate_deliveries": log.duplicate_deliveries,
        # The stale cut needs host-referenced timestamps; None means "not checked".
        "stale_at_start": log.stale_at_start if global_only else None,
        "future_stamped": log.future_stamped if global_only else None,
        "timestamp_domains": sorted(log.domains),
        "sensor_timestamp_metadata": log.has_sensor_timestamp,
        "first_frame_after_start_s": (
            round(log.first_arrival_s, 3) if log.first_arrival_s is not None else None
        ),
    }
    if n < 2:
        return out
    ts = np.asarray(log.timestamps_ms)
    intervals = np.diff(ts)
    steps = np.diff(np.asarray(log.frame_numbers))
    resets = np.flatnonzero(steps <= 0)
    span_s = (ts.max() - ts.min()) / 1000.0  # range: tolerates reordering within the run
    out["mean_fps"] = round((n - 1) / span_s, 2) if span_s > 0 else None
    out["frame_number_gaps"] = int(np.sum(steps[steps > 1] - 1))
    out["frame_number_resets"] = int(resets.size)
    out["first_reset_at_s"] = (
        round(float(ts[resets[0] + 1] - ts[0]) / 1000.0, 3) if resets.size else None
    )
    out["non_increasing_timestamps"] = int(np.sum(intervals <= 0))
    out["interval_ms"] = _percentiles(intervals)
    out["longest_interval_at_s"] = round(float(ts[int(np.argmax(intervals)) + 1] - ts[0]) / 1000.0, 3)
    if log.receive_minus_timestamp_ms:
        out["receive_minus_timestamp_ms"] = _percentiles(np.asarray(log.receive_minus_timestamp_ms))
    if log.invalid_depth_fraction:
        out["invalid_depth_fraction"] = _percentiles(np.asarray(log.invalid_depth_fraction))
    if log.motion_xyz:
        xyz = np.asarray(log.motion_xyz)
        mean = xyz.mean(axis=0)
        out["motion_mean_xyz"] = [round(float(v), 4) for v in mean]
        out["motion_mean_norm"] = round(float(np.linalg.norm(mean)), 4)
        out["motion_std_xyz"] = [round(float(v), 4) for v in xyz.std(axis=0)]
    return out


def _home_relative(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~", 1)


def sdk_build() -> dict[str, str]:
    """Identify the loaded pyrealsense2 build (PyPI wheel or source install)."""
    extension = Path(sys.modules[f"{rs.__name__}.pyrealsense2"].__file__).resolve()
    try:
        version = importlib.metadata.version("pyrealsense2")
    except importlib.metadata.PackageNotFoundError:  # source build: version in .so name
        version = extension.name.rpartition(".so.")[2] or "unknown"
    return {"pyrealsense2": version, "module_dir": _home_relative(extension.parent)}


def _enum_name(value: Any) -> str:
    return str(value).split(".")[-1]


def _open_device_nodes() -> dict[str, int]:
    """Count this process's open /dev/video* and /dev/bus/usb/* descriptors.

    /dev/video* means the kernel V4L backend; /dev/bus/usb/* without
    /dev/video* means the libusb (RSUSB) backend.
    """
    counts = {"dev_video": 0, "dev_bus_usb": 0}
    for fd in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("/dev/video"):
            counts["dev_video"] += 1
        elif target.startswith("/dev/bus/usb"):
            counts["dev_bus_usb"] += 1
    return counts


def _intrinsics(profile: rs.video_stream_profile) -> dict[str, Any]:
    i = profile.get_intrinsics()
    return {
        "width": i.width, "height": i.height, "fx": i.fx, "fy": i.fy,
        "ppx": i.ppx, "ppy": i.ppy, "model": _enum_name(i.model), "coeffs": list(i.coeffs),
    }


def _device_info(device: rs.device) -> dict[str, Any]:
    info: dict[str, Any] = {}
    fields = {
        "name": rs.camera_info.name,
        "product_line": rs.camera_info.product_line,
        "firmware_version": rs.camera_info.firmware_version,
        "recommended_firmware_version": rs.camera_info.recommended_firmware_version,
        "usb_type_descriptor": rs.camera_info.usb_type_descriptor,
    }
    for key, cam_info in fields.items():
        if device.supports(cam_info):
            info[key] = device.get_info(cam_info)
    return info


def imu_available() -> bool:
    """True if a connected device exposes accel/gyro streams (needs RSUSB or HID kernel support)."""
    motion = (rs.stream.accel, rs.stream.gyro)
    return any(
        profile.stream_type() in motion
        for device in rs.context().query_devices()
        for sensor in device.query_sensors()
        for profile in sensor.get_stream_profiles()
    )


def _calibration(profile: rs.pipeline_profile, with_imu: bool) -> dict[str, Any]:
    depth = profile.get_stream(rs.stream.depth).as_video_stream_profile()
    color = profile.get_stream(rs.stream.color).as_video_stream_profile()
    ext = depth.get_extrinsics_to(color)
    calib: dict[str, Any] = {
        "depth_intrinsics": _intrinsics(depth),
        "color_intrinsics": _intrinsics(color),
        "depth_to_color": {"rotation": list(ext.rotation), "translation_m": list(ext.translation)},
    }
    for stream in (rs.stream.accel, rs.stream.gyro) if with_imu else ():
        motion = profile.get_stream(stream).as_motion_stream_profile()
        try:
            mi = motion.get_motion_intrinsics()
            calib[f"{_enum_name(stream)}_intrinsics"] = {
                "data": [list(row) for row in mi.data],
                "noise_variances": list(mi.noise_variances),
                "bias_variances": list(mi.bias_variances),
            }
        except RuntimeError as exc:
            calib[f"{_enum_name(stream)}_intrinsics"] = f"unavailable: {exc}"
    return calib


def capture(
    seconds: float, width: int, height: int, fps: int, recording: Path | None
) -> tuple[dict[str, Any], dict[str, StreamLog], dict[str, float]]:
    """Stream (and optionally record) for `seconds`; return run info and logs."""
    config = rs.config()
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)
    with_imu = imu_available()
    if with_imu:
        config.enable_stream(rs.stream.accel)
        config.enable_stream(rs.stream.gyro)
    if recording is not None:
        recording.parent.mkdir(parents=True, exist_ok=True)
        config.enable_record_to_file(str(recording))

    logs: dict[str, StreamLog] = {}
    start = time.monotonic()
    start_wall_ms = time.time() * 1000.0 - 50.0  # 50 ms margin for clock mapping

    def record(frame: rs.frame) -> None:
        name = frame.get_profile().stream_name()
        log = logs.setdefault(name, StreamLog())
        number = frame.get_frame_number()
        ts = frame.get_timestamp()
        if (number, ts) in log.seen_frames:
            log.duplicate_deliveries += 1
            return
        log.seen_frames.add((number, ts))
        log.received += 1
        domain = frame.get_frame_timestamp_domain()
        log.domains.add(_enum_name(domain))
        if domain == rs.timestamp_domain.global_time:
            if ts < start_wall_ms:
                log.stale_at_start += 1
                return
            # Genuine samples are at most ~20 ms ahead of arrival (clock-mapping
            # error); some start-up IMU samples have been stamped far ahead.
            if ts > time.time() * 1000.0 + 1000.0:
                log.future_stamped += 1
                return
        if log.first_arrival_s is None:
            log.first_arrival_s = time.monotonic() - start
        log.timestamps_ms.append(ts)
        log.frame_numbers.append(number)
        if domain == rs.timestamp_domain.global_time:
            log.receive_minus_timestamp_ms.append(time.time() * 1000.0 - ts)
        if not log.has_sensor_timestamp:
            log.has_sensor_timestamp = frame.supports_frame_metadata(
                rs.frame_metadata_value.sensor_timestamp
            )
        if frame.is_depth_frame():
            depth = np.asanyarray(frame.get_data())
            log.invalid_depth_fraction.append(1.0 - np.count_nonzero(depth) / depth.size)
        elif frame.is_motion_frame():
            v = frame.as_motion_frame().get_motion_data()
            log.motion_xyz.append((v.x, v.y, v.z))

    def on_frame(frame: rs.frame) -> None:
        if frame.is_frameset():
            frameset = frame.as_frameset()
            for i in range(frameset.size()):
                record(frameset[i])
        else:
            record(frame)

    pipeline = rs.pipeline()
    profile = pipeline.start(config, on_frame)
    try:
        time.sleep(seconds)
        nodes = _open_device_nodes()
    finally:
        pipeline.stop()

    device = profile.get_device()
    nominal = {
        s.stream_name(): float(s.fps()) for s in profile.get_streams()
    }
    run = {
        "device": _device_info(device),
        "depth_scale_m": device.first_depth_sensor().get_depth_scale(),
        "profiles": [
            {"stream": s.stream_name(), "format": _enum_name(s.format()), "fps": s.fps()}
            | ({"width": s.as_video_stream_profile().width(),
                "height": s.as_video_stream_profile().height()} if s.is_video_stream_profile() else {})
            for s in profile.get_streams()
        ],
        "imu_exposed": with_imu,
        "calibration": _calibration(profile, with_imu),
        "open_device_nodes": nodes,
    }
    return run, logs, nominal


def replay_frame_counts(
    recording: Path, idle_s: float = 5.0, limit_s: float = 300.0
) -> tuple[dict[str, int], bool]:
    """Play a recording once at sensor level and count distinct frames per stream.

    The pipeline's syncer groups frames and drops some, so playback goes through
    each recorded sensor directly. Frames are counted by (number, timestamp)
    because frame counters can restart. Returns the counts and whether playback
    reported reaching the end of the file.
    """
    device = rs.context().load_device(str(recording))
    playback = device.as_playback()
    playback.set_real_time(False)
    seen: dict[str, set[tuple[int, float]]] = {}
    started, finished = threading.Event(), threading.Event()

    def on_status(status: rs.playback_status) -> None:
        if status == rs.playback_status.playing:
            started.set()
        elif status == rs.playback_status.stopped and started.is_set():
            finished.set()

    def on_frame(frame: rs.frame) -> None:
        key = (frame.get_frame_number(), frame.get_timestamp())
        seen.setdefault(frame.get_profile().stream_name(), set()).add(key)

    playback.set_status_changed_callback(on_status)
    # A recorded device can contain sensors that were not streamed; opening those fails.
    sensors = [s for s in device.query_sensors() if s.get_stream_profiles()]
    opened: list[rs.sensor] = []
    running: list[rs.sensor] = []
    reached_end = False
    try:
        for sensor in sensors:
            sensor.open(sensor.get_stream_profiles())
            opened.append(sensor)
        for sensor in opened:
            sensor.start(on_frame)
            running.append(sensor)
        deadline, last_total, last_change = time.monotonic() + limit_s, -1, time.monotonic()
        while not finished.is_set() and time.monotonic() < deadline:
            time.sleep(0.5)
            total = sum(map(len, list(seen.values())))  # snapshot: callbacks may add a stream
            if total != last_total:
                last_total, last_change = total, time.monotonic()
            elif time.monotonic() - last_change > idle_s:
                break
        reached_end = finished.is_set()  # read before stop(): stopping also reports STOPPED
    finally:
        for sensor in running:
            sensor.stop()
        for sensor in opened:
            sensor.close()
    return {name: len(frames) for name, frames in seen.items()}, reached_end


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--width", type=int, default=848)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--record", type=Path, help="record to this new .db3 file and read it back")
    args = parser.parse_args()
    recording = args.record.expanduser() if args.record else None
    if recording is not None and recording.exists():
        parser.error(f"{_home_relative(recording)} already exists; use a new session name")

    run, logs, nominal = capture(args.seconds, args.width, args.height, args.fps, recording)
    summary: dict[str, Any] = {
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "versions": {**sdk_build(), "numpy": np.__version__},
        "requested_seconds": args.seconds,
        **run,
        "streams": {
            name: summarize(logs.get(name, StreamLog()), nominal.get(name, 0.0))
            for name in sorted(set(nominal) | set(logs))
        },
    }
    if recording is not None:
        delivered = {
            name: logs[name].received if name in logs else 0
            for name in sorted(set(nominal) | set(logs))
        }
        result: dict[str, Any] = {
            "path": _home_relative(recording),
            "bytes": recording.stat().st_size,
            "delivered_frames": delivered,  # distinct frames the callback received, stale included
        }
        try:
            recorded, complete = replay_frame_counts(recording)
        except RuntimeError as exc:
            result["replay_error"] = str(exc)
        else:
            result["recorded_frames"] = recorded  # distinct frames read back per sensor
            result["replay_complete"] = complete
            result["recorded_not_delivered"] = {
                name: recorded.get(name, 0) - delivered.get(name, 0)
                for name in sorted(set(recorded) | set(delivered))
            } if complete else None
        summary["recording"] = result
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
