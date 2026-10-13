"""SIMULATION ONLY: an in-memory stand-in for the UGV01 board. No hardware access.

``SimulatedUGV01`` implements the ``Transport`` interface entirely in memory.
It models what the adapter relies on, as read from ugv_base_general 0.9x
source for the closed-loop UGV01 path (mainType 3), not as measured on the
robot:

- one JSON command per ``\\n`` line; unparsable lines are dropped silently;
- echo of every parsed line (exact bytes) before it is handled, on by default;
- ``{"T":1}`` sets track setpoints only if L and R are both numbers; if so it
  refreshes the heartbeat *before* the range check, and |L| or |R| > 2.0 m/s
  is ignored (previous setpoint kept), not clamped;
- ``{"T":130}`` answers with one CRLF-terminated T:1001 line;
  ``{"T":143,"cmd":0/1}`` switches the echo; other ``T`` codes do nothing;
- the heartbeat: once more than ``heartbeat_timeout_s`` has passed since the
  last accepted-shape T:1, setpoints become zero (once, until the next T:1).
  Feedback requests do not refresh it.

Idealised: speeds equal setpoints instantly (no PID, decel, noise or
quantisation); no boot log, Wi-Fi, IMU or rate limiter. Time comes from an
injected clock and nothing here sleeps.
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from .protocol import (
    FIRMWARE_HEARTBEAT_TIMEOUT_S,
    FIRMWARE_IGNORED_ABOVE_M_PER_S,
    LineSplitter,
    check_frame,
)


class ManualClock:
    """A monotonic clock advanced by hand, for simulations and tests."""

    def __init__(self, start_s: float = 0.0) -> None:
        if not math.isfinite(start_s):
            raise ValueError("start_s must be finite")
        self._now_s = start_s

    def __call__(self) -> float:
        """Return the current simulated time in seconds."""
        return self._now_s

    def advance(self, dt_s: float) -> float:
        """Move time forward by ``dt_s`` (>= 0) seconds and return the new time."""
        if not (math.isfinite(dt_s) and dt_s >= 0):
            raise ValueError("dt_s must be finite and >= 0")
        self._now_s += dt_s
        return self._now_s


@dataclass(frozen=True, slots=True)
class SimMotionEvent:
    """A T:1 the simulated board received; ``applied`` is False if ignored as out of range."""

    time_s: float
    left_m_per_s: float
    right_m_per_s: float
    applied: bool


def _number(value: object) -> float | None:
    """Mimic ArduinoJson ``is<float>()``: any JSON number counts, bools and strings do not."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        return float("inf")


class SimulatedUGV01:
    """SIMULATION ONLY: in-memory UGV01 board behind the ``Transport`` interface."""

    source_mode: Final = "simulation"

    def __init__(
        self,
        clock: Callable[[], float],
        *,
        heartbeat_timeout_s: float = FIRMWARE_HEARTBEAT_TIMEOUT_S,
        echo: bool = True,
    ) -> None:
        self._clock = clock
        self._heartbeat_timeout_s = heartbeat_timeout_s
        self._echo = echo
        self._setpoints_m_per_s = (0.0, 0.0)
        self._last_motion_command_s = clock()
        self._heartbeat_latched = True  # nothing to stop at start
        self._splitter = LineSplitter()
        self._outbox: deque[bytes] = deque()
        self._link_up = True
        self._disconnected = False
        self._closed = False
        self.host_lines: list[bytes] = []
        """Every line the host wrote while the transport was open, in order (some may have been lost)."""
        self.motion_log: list[SimMotionEvent] = []
        """Every T:1 that reached the board, in order."""
        self.heartbeat_stops = 0
        """How many times the heartbeat zeroed the setpoints."""

    # --- Transport interface -------------------------------------------------

    def write_line(self, line: bytes) -> None:
        """Deliver one host line to the simulated board (dropped while the link is down)."""
        self._check_io()
        check_frame(line)
        self.host_lines.append(line)
        self._advance()
        if self._link_up:
            self._handle(line)

    def read_line(self, timeout_s: float) -> bytes | None:
        """Return the next board line, or None. Never waits: simulated time only moves via the clock."""
        self._check_io()
        self._advance()
        return self._outbox.popleft() if self._outbox else None

    def close(self) -> None:
        """Close the simulated link; further I/O raises ConnectionError."""
        self._closed = True

    # --- Simulation controls -------------------------------------------------

    def set_link_up(self, up: bool) -> None:
        """While False, silently drop traffic in both directions (like a cut UART wire)."""
        self._link_up = up

    def set_disconnected(self, disconnected: bool) -> None:
        """While True, every I/O call raises ConnectionError (like an unplugged USB adapter)."""
        self._disconnected = disconnected

    def inject_output(self, raw: bytes) -> None:
        """Queue raw board output (noise, partial or glued lines); lost while the link is down."""
        if self._link_up:
            self._emit(raw)

    def track_speeds_m_per_s(self) -> tuple[float, float]:
        """Current (left, right) track speeds in m/s after applying the heartbeat."""
        self._advance()
        return self._setpoints_m_per_s

    # --- Board behaviour -----------------------------------------------------

    def _check_io(self) -> None:
        if self._closed:
            raise ConnectionError("simulated transport is closed")
        if self._disconnected:
            raise ConnectionError("simulated disconnect")

    def _emit(self, raw: bytes) -> None:
        self._outbox.extend(self._splitter.feed(raw))

    def _advance(self) -> None:
        elapsed_s = self._clock() - self._last_motion_command_s
        if not self._heartbeat_latched and elapsed_s > self._heartbeat_timeout_s:
            self._setpoints_m_per_s = (0.0, 0.0)
            self._heartbeat_latched = True
            self.heartbeat_stops += 1

    def _handle(self, line: bytes) -> None:
        try:
            command, _ = json.JSONDecoder().raw_decode(line.decode("utf-8", errors="replace").lstrip())
        except (ValueError, RecursionError):
            return  # parse errors are dropped without echo or reply
        if self._echo:
            self._emit(line)  # exact received bytes, printed before the command runs
        if not isinstance(command, dict):
            return
        kind = command.get("T")
        if kind == 1:
            self._speed_ctrl(command)
        elif kind == 130:
            self._emit(self._base_feedback_line())
        elif kind == 143:
            self._echo = bool(command.get("cmd"))

    def _speed_ctrl(self, command: dict[str, object]) -> None:
        left, right = _number(command.get("L")), _number(command.get("R"))
        if left is None or right is None:
            return  # no-op that also leaves the heartbeat alone
        now_s = self._clock()
        self._last_motion_command_s = now_s
        self._heartbeat_latched = False
        applied = abs(left) <= FIRMWARE_IGNORED_ABOVE_M_PER_S and abs(right) <= FIRMWARE_IGNORED_ABOVE_M_PER_S
        if applied:
            self._setpoints_m_per_s = (left, right)
        self.motion_log.append(SimMotionEvent(now_s, left, right, applied))

    def _base_feedback_line(self) -> bytes:
        left, right = self._setpoints_m_per_s
        payload = {"T": 1001, "L": left, "R": right, "r": 0.0, "p": 0.0, "y": 0.0, "temp": 40.0, "v": 11.7}
        return (json.dumps(payload, separators=(",", ":")) + "\r\n").encode("ascii")
