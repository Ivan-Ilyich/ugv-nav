#!/usr/bin/env python3
"""READ-ONLY first-contact probe for the UGV01 driver board over serial or Wi-Fi.

Sends no motion command. The only bytes it writes are STOP
(``{"T":1,"L":0.0,"R":0.0}``) and one-shot feedback requests (T:139 speed
rate, T:126 IMU, T:130 chassis feedback). It changes no board setting: echo,
debug text, feedback stream, heartbeat, main type and Wi-Fi stay as they are.

Opening the board's USB-C port may reboot it: the CP2102's DTR/RTS lines
drive the ESP32 reset and boot pins. The transport clears RTS then DTR after
opening (Waveshare's order); whether opening still resets the board must be
measured (a ROM boot banner during the passive listen means it did). The
40-pin UART has no DTR/RTS path.

Sequence:
1. Open the port (115200 8N1) and only listen for ``--listen-s`` seconds
   (default 25), stopping early at a boot-mission marker. Any byte received
   from serial start-up until the boot mission ends (several seconds; longer
   in Wi-Fi STA mode) aborts that mission. Without a marker the probe warns.
2. Send STOP once, then T:139 and T:126 once, then T:130 ``--samples`` times.
3. Send STOP again and close the port.

Every received line is printed with seconds since opening, after masking
Wi-Fi passwords/SSIDs, MAC and IP addresses (the firmware prints them). A JSON
summary follows. Signatures it helps check: echoed host lines and T:1001
replies mean the ugv_base_general family; ``raw_non_printable_bytes`` close to
``raw_bytes`` with few or no complete lines suggests a baud mismatch (the older
UGV01_BASE firmware runs at 1,000,000); a 'temp' key in T:1001 suggests a build
newer than 0.90. ``unsolicited_base_feedback`` counts valid T:1001 that arrived
before the probe sent anything: if it is not zero, the T:131 stream or another
host is active, and polled feedback is no proof that the host's bytes arrive.

Over Wi-Fi (``--http``) the same commands go to the firmware's HTTP endpoint
``GET http://<host>/js?json=<command>``. There is no boot text, echo or
unsolicited output on that path, so the passive listen is skipped, and the
summary adds request counts and round-trip times instead of raw serial counts.

This is a hardware action: run it with the tracks off the ground. Wi-Fi
first contact (Mac, curl, 19 October 2026) succeeded; the serial route is
unverified (the printed mount covers the Jetson's 40-pin header):

    uv run python tools/ugv01_probe.py --http <board address>
    uv run python tools/ugv01_probe.py --port <serial device>

Exit status: 0 if at least one valid T:1001 arrived, 2 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ugv_nav.ugv01.protocol import (
    STOP,
    BaseFeedback,
    Command,
    FeedbackRequest,
    ImuFeedback,
    SpeedRateReport,
    WheelSpeedCommand,
    encode_command,
    extract_json_objects,
    parse_feedback_line,
    redact_for_log,
)
from ugv_nav.ugv01.transport import HttpTransport, SerialTransport, Transport

BOOT_MARKERS = ("[missionPlay finished.]", "[missionPlay abort.]")


@dataclass
class ProbeLog:
    """Counts and observations collected while probing."""

    start_s: float
    sent: set[bytes] = field(default_factory=set)
    lines: int = 0
    non_ascii_bytes: int = 0
    echo_lines: int = 0
    boot_markers: list[str] = field(default_factory=list)
    base_valid: int = 0
    base_before_first_send: int = 0
    base_invalid: list[str] = field(default_factory=list)
    base_keys: set[str] = field(default_factory=set)
    last_base: BaseFeedback | None = None
    imu: ImuFeedback | None = None
    speed_rate: SpeedRateReport | None = None

    def record(self, line: bytes, now_s: float) -> None:
        """Print one received line (redacted) and update the counts."""
        self.lines += 1
        self.non_ascii_bytes += sum(1 for byte in line if byte > 0x7E or (byte < 0x20 and byte != 0x09))
        text = line.decode("utf-8", errors="backslashreplace")
        print(f"{now_s - self.start_s:8.3f} << {redact_for_log(text)}", flush=True)
        if line + b"\n" in self.sent:
            self.echo_lines += 1
            return
        self.boot_markers += [marker for marker in BOOT_MARKERS if marker in text]
        for obj in extract_json_objects(text):
            if obj.get("T") == 1001:
                self.base_keys.update(obj)
        for message in parse_feedback_line(line, received_monotonic_s=now_s, source="hardware"):
            if isinstance(message, BaseFeedback):
                if message.valid:
                    self.base_valid += 1
                    if not self.sent:
                        self.base_before_first_send += 1
                    self.last_base = message
                else:
                    self.base_invalid.append(message.problem or "invalid")
            elif isinstance(message, ImuFeedback):
                self.imu = message
            else:
                self.speed_rate = message

    def summary(self) -> dict[str, object]:
        """JSON-ready summary without raw text (no addresses or credentials)."""
        base = self.last_base
        return {
            "lines": self.lines,
            "non_ascii_bytes": self.non_ascii_bytes,
            "echo_lines": self.echo_lines,
            "boot_markers": self.boot_markers,
            "base_feedback_valid": self.base_valid,
            "unsolicited_base_feedback": self.base_before_first_send,
            "base_feedback_invalid": self.base_invalid[:5],
            "base_feedback_keys": sorted(self.base_keys),
            "last_base_feedback": None
            if base is None
            else {
                "left_m_per_s": base.left_m_per_s,
                "right_m_per_s": base.right_m_per_s,
                "roll_deg": base.roll_deg,
                "pitch_deg": base.pitch_deg,
                "yaw_deg": base.yaw_deg,
                "battery_v": base.battery_v,
                "esp32_temp_c": base.esp32_temp_c,
            },
            "imu_valid": None if self.imu is None else self.imu.valid,
            "speed_rate": None
            if self.speed_rate is None
            else [self.speed_rate.left_rate, self.speed_rate.right_rate],
        }


def send(transport: Transport, command: Command, log: ProbeLog) -> None:
    """Write a stop or feedback request; refuse anything that could move the robot."""
    if isinstance(command, WheelSpeedCommand) and not command.is_stop:
        raise RuntimeError("the probe never sends motion commands")
    line = encode_command(command)
    log.sent.add(line)
    transport.write_line(line)
    print(f"{time.monotonic() - log.start_s:8.3f} >> {line.decode('ascii').strip()}", flush=True)


def listen(transport: Transport, duration_s: float, log: ProbeLog, *, until_boot_marker: bool = False) -> None:
    """Print incoming lines for ``duration_s`` (optionally stop early at a boot-mission marker)."""
    deadline_s = time.monotonic() + duration_s
    while (remaining_s := deadline_s - time.monotonic()) > 0:
        line = transport.read_line(min(remaining_s, 0.05))
        if line is not None:
            log.record(line, time.monotonic())
            if until_boot_marker and log.boot_markers:
                return


def bounded[N: (int, float)](kind: type[N], low: N, high: N) -> Callable[[str], N]:
    """argparse type: a number of ``kind`` within [low, high]."""

    def parse(text: str) -> N:
        value = kind(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be in [{low}, {high}]")
        return value

    return parse


def run_probe(
    transport: Transport,
    *,
    listen_s: float,
    samples: int,
    interval_s: float,
    log: ProbeLog,
    expect_boot_text: bool = True,
) -> None:
    """Listen first, then send only STOP and one-shot feedback requests; always end with STOP.

    ``expect_boot_text=False`` (HTTP) skips the boot-marker warning: that path never carries boot text.
    """
    try:
        listen(transport, listen_s, log, until_boot_marker=True)
        if expect_boot_text and not log.boot_markers:
            print(
                "no boot-mission marker seen: the board booted earlier, debug text is off, "
                "or it is still booting; the next byte may abort /boot.mission",
                file=sys.stderr,
            )
        if log.base_before_first_send:
            print(
                f"warning: {log.base_before_first_send} T:1001 arrived before the probe sent "
                "anything: the T:131 stream or another host is active, so link health is not "
                "a round trip",
                file=sys.stderr,
            )
        send(transport, STOP, log)
        listen(transport, interval_s, log)
        for request in (FeedbackRequest.SPEED_RATE, FeedbackRequest.IMU):
            send(transport, request, log)
            listen(transport, interval_s, log)
        for _ in range(samples):
            send(transport, FeedbackRequest.BASE, log)
            listen(transport, interval_s, log)
    finally:
        try:
            send(transport, STOP, log)
            listen(transport, interval_s, log)
        except OSError as error:
            print(f"final stop failed: {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    link = parser.add_mutually_exclusive_group(required=True)
    link.add_argument("--port", help="serial device of the board's UART0")
    link.add_argument("--http", metavar="HOST", help="board address on Wi-Fi (firmware HTTP endpoint)")
    parser.add_argument("--listen-s", type=bounded(float, 0.0, 60.0), default=25.0, help="passive listen first (serial only)")
    parser.add_argument("--samples", type=bounded(int, 1, 100), default=10, help="number of T:130 requests")
    parser.add_argument("--interval-s", type=bounded(float, 0.05, 2.0), default=0.2, help="request spacing")
    args = parser.parse_args()

    log = ProbeLog(start_s=time.monotonic())
    link_summary: dict[str, object]
    if args.http is not None:
        with HttpTransport(args.http) as http:
            run_probe(http, listen_s=0.0, samples=args.samples, interval_s=args.interval_s, log=log, expect_boot_text=False)
        link_summary = {
            "link": "http",
            "requests": http.requests,
            "failed_requests": http.failed_requests,
            "overflowed_replies": http.overflowed_replies,
            "last_round_trip_s": http.last_round_trip_s,
            "max_round_trip_s": http.max_round_trip_s,
        }
    else:
        with SerialTransport.open(args.port) as serial_link:
            run_probe(serial_link, listen_s=args.listen_s, samples=args.samples, interval_s=args.interval_s, log=log)
        link_summary = {
            "link": "serial",
            "raw_bytes": serial_link.bytes_received,
            "raw_non_printable_bytes": serial_link.non_printable_bytes,
            "overflowed_lines": serial_link.overflowed_lines,
            "unterminated_bytes": serial_link.pending_bytes,
        }
    print(json.dumps(log.summary() | link_summary, indent=2))
    return 0 if log.base_valid else 2


if __name__ == "__main__":
    sys.exit(main())
