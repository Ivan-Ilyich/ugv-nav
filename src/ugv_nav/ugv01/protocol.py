"""Pure encoding and parsing for the UGV01 JSON-line serial protocol (no I/O).

Protocol facts come from waveshareteam/ugv_base_general @ d308df9 (GPL-3.0),
read as documentation only; no firmware code is copied here. None of it has
been checked against this robot yet. See docs/ugv01-protocol.md.

Wire format: the host sends one JSON object per line, terminated by ``\\n``.
The board answers with CRLF-terminated JSON lines interleaved with an echo of
every parsed host line, plain-text debug output, and a Wi-Fi status object
(T:405) that has no line terminator at all. The parser below therefore
extracts JSON objects from arbitrary text and never raises on malformed input.

Units are carried in names: ``_m_per_s`` (metres per second), ``_deg``
(degrees), ``_v`` (volts), ``_c`` (degrees Celsius), ``_s`` (seconds).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Final, Literal

SourceMode = Literal["hardware", "simulation"]
"""Where a message came from; simulated data must never be mistaken for robot data."""

SERIAL_BAUD_RATE: Final = 115_200
"""UART0 rate in ugv_base_general (8N1). 1,000,000 would mean the older UGV01_BASE firmware."""

FIRMWARE_HEARTBEAT_TIMEOUT_S: Final = 3.0
"""Firmware default: motion stops this long after the last T:1/T:11/T:13 (strictly greater)."""

FIRMWARE_IGNORED_ABOVE_M_PER_S: Final = 2.0
"""On the closed-loop path, a T:1 with |L| or |R| above this is ignored, not clamped."""

ABSOLUTE_SPEED_CAP_M_PER_S: Final = 0.5
"""Highest cap this adapter accepts: the wiki's T:1 range, and full PWM duty if the
board were on an open-loop main type (duty = value x 512)."""

DEFAULT_SPEED_CAP_M_PER_S: Final = 0.10
"""Default host-side cap: 20 % of the wiki range; about 20 % duty even on an open-loop main type."""

MAX_PLAUSIBLE_FEEDBACK_SPEED_M_PER_S: Final = 2.5
"""Feedback speeds beyond this are flagged invalid (e.g. PWM counts reported on open-loop types)."""

MAX_LINE_BYTES: Final = 1024
"""Longest board line kept by ``LineSplitter``; real lines are a few hundred bytes."""


class CommandType(IntEnum):
    """Host-to-board ``T`` codes this adapter may send (an allow-list by construction)."""

    SPEED_CTRL = 1
    GET_IMU_DATA = 126
    BASE_FEEDBACK = 130
    GET_SPEED_RATE = 139


class FeedbackType(IntEnum):
    """Board-to-host ``T`` codes this adapter parses."""

    BASE = 1001
    IMU = 1002
    SPEED_RATE = 139


class CommandRejected(ValueError):
    """A command failed validation and was not encoded."""


@dataclass(frozen=True, slots=True)
class WheelSpeedCommand:
    """Left/right track speed setpoints for ``{"T":1,"L":..,"R":..}`` (CMD_SPEED_CTRL).

    Units are metres per second on the firmware's closed-loop UGV01 path
    (mainType 3). Positive means forward according to the Waveshare wiki; the
    sign convention and left/right mapping are unverified on this robot.

    Construction does not validate, so a guard can record a bad command as a
    fault; ``wheel_speed_problem`` and ``encode_command`` do the checking.
    """

    left_m_per_s: float
    right_m_per_s: float

    @property
    def is_stop(self) -> bool:
        """True when both setpoints are exactly zero."""
        return self.left_m_per_s == 0 and self.right_m_per_s == 0


STOP: Final = WheelSpeedCommand(0.0, 0.0)
"""The normal stop: ``{"T":1,"L":0.0,"R":0.0}``. There is no latched stop in this firmware."""


class FeedbackRequest(Enum):
    """One-shot read requests. None of them moves the robot or refreshes the firmware heartbeat."""

    BASE = CommandType.BASE_FEEDBACK  # reply: T:1001
    IMU = CommandType.GET_IMU_DATA  # reply: T:1002
    SPEED_RATE = CommandType.GET_SPEED_RATE  # reply: T:139


Command = WheelSpeedCommand | FeedbackRequest


def _as_finite_float(value: object) -> float | None:
    """Return ``value`` as a finite float, or None for bools, non-numbers, NaN and infinities."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:  # int too large for a float
        return None
    return number if math.isfinite(number) else None


def check_speed_cap(speed_cap_m_per_s: float) -> float:
    """Return the cap as a float if ``0 < cap <= ABSOLUTE_SPEED_CAP_M_PER_S``; raise ValueError otherwise."""
    cap = _as_finite_float(speed_cap_m_per_s)
    if cap is None or not 0.0 < cap <= ABSOLUTE_SPEED_CAP_M_PER_S:
        raise ValueError(
            f"speed cap must be in (0, {ABSOLUTE_SPEED_CAP_M_PER_S}] m/s, got {speed_cap_m_per_s!r}"
        )
    return cap


def wheel_speed_problem(command: WheelSpeedCommand, speed_cap_m_per_s: float) -> str | None:
    """Return why ``command`` must not be sent, or None if both speeds are finite and within the cap.

    Out-of-cap values are rejected rather than clamped: a value above the cap
    signals a caller bug or a unit mix-up (mm/s, PWM), and clamping each track
    independently would also change the commanded turn ratio.
    """
    cap = check_speed_cap(speed_cap_m_per_s)
    for side, value in (("left", command.left_m_per_s), ("right", command.right_m_per_s)):
        number = _as_finite_float(value)
        if number is None:
            return f"{side} speed is not a finite number: {value!r}"
        if abs(number) > cap:
            return f"{side} speed {number} m/s exceeds the {cap} m/s cap"
    return None


def _wire_float(value: float) -> float:
    """Normalise a validated speed for the wire (float, and -0.0 becomes 0.0)."""
    return float(value) + 0.0


def encode_command(
    command: Command, *, speed_cap_m_per_s: float = DEFAULT_SPEED_CAP_M_PER_S
) -> bytes:
    """Encode one command as a single ASCII JSON line ending in ``\\n``.

    Raises ``CommandRejected`` for non-finite or out-of-cap wheel speeds and for
    any type outside the allow-list, so out-of-bounds bytes are never produced.
    """
    payload: dict[str, int | float]
    if isinstance(command, WheelSpeedCommand):
        problem = wheel_speed_problem(command, speed_cap_m_per_s)
        if problem is not None:
            raise CommandRejected(problem)
        payload = {
            "T": int(CommandType.SPEED_CTRL),
            "L": _wire_float(command.left_m_per_s),
            "R": _wire_float(command.right_m_per_s),
        }
    elif isinstance(command, FeedbackRequest):
        payload = {"T": int(command.value)}
    else:
        raise CommandRejected(f"unsupported command type: {type(command).__name__}")
    text = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    return (text + "\n").encode("ascii")


@dataclass(frozen=True, slots=True)
class BaseFeedback:
    """Chassis feedback ``{"T":1001,...}``.

    ``left_m_per_s``/``right_m_per_s`` are the firmware's per-loop track speed
    estimates (closed-loop UGV01 path; noisy, about 0.03 m/s quantisation;
    sign and side mapping unverified). ``roll_deg``/``pitch_deg``/``yaw_deg`` are
    the board AHRS in degrees, in an unverified sensor frame; yaw is
    magnetometer-based and uncalibrated. ``battery_v`` may be up to 10 s stale.
    ``esp32_temp_c`` is the ESP32 die temperature, not the IMU, and is absent on
    older builds. The board sends no timestamp: ``received_monotonic_s`` is host
    monotonic time at receipt (or at the tick that read the line).

    ``valid`` is False when either speed is missing, non-numeric, non-finite or
    implausible; ``problem`` then says why and the speed fields may be None.
    Optional fields are None when absent or not finite (builds from b113287,
    May 2024, still labelled 0.90, send ``"y":"null"``; earlier 0.90 builds,
    likely the factory image, and later builds send a numeric y); that alone
    does not make the message invalid.
    """

    left_m_per_s: float | None
    right_m_per_s: float | None
    roll_deg: float | None
    pitch_deg: float | None
    yaw_deg: float | None
    battery_v: float | None
    esp32_temp_c: float | None
    received_monotonic_s: float
    source: SourceMode
    valid: bool
    problem: str | None = None

    @property
    def stationary(self) -> bool:
        """True when the message is valid and both track speeds are exactly zero."""
        return self.valid and self.left_m_per_s == 0 and self.right_m_per_s == 0


Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ImuFeedback:
    """Board IMU reply ``{"T":1002,...}`` in an unverified sensor frame.

    Accelerometer in milli-g, gyroscope in deg/s, magnetometer in approximately
    microtesla (raw x 0.15, with a hard-coded offset). ``valid`` requires finite
    accelerometer and gyroscope triples.
    """

    roll_deg: float | None
    pitch_deg: float | None
    yaw_deg: float | None
    accel_mg: Vector3 | None
    gyro_deg_per_s: Vector3 | None
    mag_ut: Vector3 | None
    received_monotonic_s: float
    source: SourceMode
    valid: bool
    problem: str | None = None


@dataclass(frozen=True, slots=True)
class SpeedRateReport:
    """Reply ``{"T":139,"L":..,"R":..}``: firmware per-side speed multipliers (0..1, dimensionless)."""

    left_rate: float | None
    right_rate: float | None
    received_monotonic_s: float
    source: SourceMode
    valid: bool
    problem: str | None = None


Feedback = BaseFeedback | ImuFeedback | SpeedRateReport


def extract_json_objects(text: str) -> list[dict[str, object]]:
    """Return every JSON object embedded in ``text``, in order. Never raises.

    Skips text before, between and after objects, partial objects, and splits
    objects glued together without a newline.
    """
    decoder = json.JSONDecoder()
    objects: list[dict[str, object]] = []
    index = text.find("{")
    while index != -1:
        try:
            value, end = decoder.raw_decode(text, index)
        except (ValueError, RecursionError):
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict):
            objects.append(value)
        index = text.find("{", end)
    return objects


def _vector(obj: dict[str, object], keys: tuple[str, str, str]) -> Vector3 | None:
    x, y, z = (_as_finite_float(obj.get(key)) for key in keys)
    if x is None or y is None or z is None:
        return None
    return (x, y, z)


def _track_speed(obj: dict[str, object], key: str) -> tuple[float | None, str | None]:
    if key not in obj:
        return None, f"{key} missing"
    number = _as_finite_float(obj[key])
    if number is None:
        return None, f"{key} is not a finite number: {obj[key]!r}"
    if abs(number) > MAX_PLAUSIBLE_FEEDBACK_SPEED_M_PER_S:
        return None, f"{key} = {number} is not a plausible speed in m/s"
    return number, None


def _parse_base(obj: dict[str, object], received_monotonic_s: float, source: SourceMode) -> BaseFeedback:
    left, left_problem = _track_speed(obj, "L")
    right, right_problem = _track_speed(obj, "R")
    problem = left_problem or right_problem
    return BaseFeedback(
        left_m_per_s=left,
        right_m_per_s=right,
        roll_deg=_as_finite_float(obj.get("r")),
        pitch_deg=_as_finite_float(obj.get("p")),
        yaw_deg=_as_finite_float(obj.get("y")),
        battery_v=_as_finite_float(obj.get("v")),
        esp32_temp_c=_as_finite_float(obj.get("temp")),
        received_monotonic_s=received_monotonic_s,
        source=source,
        valid=problem is None,
        problem=problem,
    )


def _parse_imu(obj: dict[str, object], received_monotonic_s: float, source: SourceMode) -> ImuFeedback:
    accel = _vector(obj, ("ax", "ay", "az"))
    gyro = _vector(obj, ("gx", "gy", "gz"))
    problem = None
    if accel is None or gyro is None:
        problem = "accelerometer or gyroscope missing or not finite"
    return ImuFeedback(
        roll_deg=_as_finite_float(obj.get("r")),
        pitch_deg=_as_finite_float(obj.get("p")),
        yaw_deg=_as_finite_float(obj.get("y")),
        accel_mg=accel,
        gyro_deg_per_s=gyro,
        mag_ut=_vector(obj, ("mx", "my", "mz")),
        received_monotonic_s=received_monotonic_s,
        source=source,
        valid=problem is None,
        problem=problem,
    )


def _parse_speed_rate(
    obj: dict[str, object], received_monotonic_s: float, source: SourceMode
) -> SpeedRateReport:
    left = _as_finite_float(obj.get("L"))
    right = _as_finite_float(obj.get("R"))
    in_range = left is not None and right is not None and 0.0 <= left <= 1.0 and 0.0 <= right <= 1.0
    return SpeedRateReport(
        left_rate=left,
        right_rate=right,
        received_monotonic_s=received_monotonic_s,
        source=source,
        valid=in_range,
        problem=None if in_range else "L/R missing or outside 0..1",
    )


def parse_feedback_line(
    line: bytes | str, *, received_monotonic_s: float, source: SourceMode
) -> list[Feedback]:
    """Parse one board line into typed feedback messages. Never raises.

    Returns an empty list for debug text, partial lines and other JSON. The
    board's echo of host commands carries the host's own ``T`` (1, 126, 130,
    139 without L/R) and is therefore never returned as feedback.
    """
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    messages: list[Feedback] = []
    for obj in extract_json_objects(text):
        kind = obj.get("T")
        if type(kind) is not int:
            continue
        if kind == FeedbackType.BASE:
            messages.append(_parse_base(obj, received_monotonic_s, source))
        elif kind == FeedbackType.IMU:
            messages.append(_parse_imu(obj, received_monotonic_s, source))
        elif kind == FeedbackType.SPEED_RATE and ("L" in obj or "R" in obj):
            messages.append(_parse_speed_rate(obj, received_monotonic_s, source))
    return messages


def check_frame(line: bytes) -> None:
    """Raise ValueError unless ``line`` is exactly one line: non-empty and ending in its only ``\\n``."""
    if not line.endswith(b"\n") or line.count(b"\n") != 1 or len(line) < 2:
        raise ValueError(f"not a single newline-terminated line: {line[:80]!r}")


class LineSplitter:
    """Reassemble lines from arbitrary byte chunks (pure; used by transports).

    Returns lines without their ``\\r\\n``/``\\n`` terminator and skips empty
    lines. A line longer than ``max_line_bytes`` is discarded up to its next
    newline and counted in ``overflowed_lines``, bounding memory use.
    """

    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        if max_line_bytes < 1:
            raise ValueError("max_line_bytes must be positive")
        self._max_line_bytes = max_line_bytes
        self._buffer = bytearray()
        self._discarding = False
        self.overflowed_lines = 0

    @property
    def pending_bytes(self) -> int:
        """Bytes of an unfinished line held until its newline arrives."""
        return len(self._buffer)

    def feed(self, data: bytes) -> list[bytes]:
        """Add received bytes; return the complete lines they finish, in order."""
        self._buffer.extend(data)
        lines: list[bytes] = []
        while (newline := self._buffer.find(b"\n")) != -1:
            raw = bytes(self._buffer[:newline]).rstrip(b"\r")
            del self._buffer[: newline + 1]
            if self._discarding:
                self._discarding = False
            elif len(raw) > self._max_line_bytes:
                self.overflowed_lines += 1
            elif raw:
                lines.append(raw)
        if len(self._buffer) > self._max_line_bytes:
            self._buffer.clear()
            if not self._discarding:
                self.overflowed_lines += 1
            self._discarding = True
        return lines


_SECRET_VALUE = re.compile(
    r'("[^"]*(?:password|ssid)[^"]*"\s*:\s*)"(?:[^"\\]|\\.?)*(?:"|$)', re.IGNORECASE
)
_MAC_ADDRESS = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
_IPV4_ADDRESS = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def redact_for_log(text: str) -> str:
    """Mask Wi-Fi passwords/SSIDs, MAC addresses and IPv4 addresses before printing board output.

    The firmware prints its Wi-Fi config (including plaintext passwords) at boot
    and in T:405 replies, and its MAC address at boot.
    """
    text = _SECRET_VALUE.sub(r'\1"<redacted>"', text)
    text = _MAC_ADDRESS.sub("<mac>", text)
    return _IPV4_ADDRESS.sub("<ip>", text)
