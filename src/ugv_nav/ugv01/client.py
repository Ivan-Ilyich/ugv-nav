"""UGV01Client: drives any ``Transport`` from the ``MotionGuard``'s output.

Motion only passes through the guard. Time comes from the client's injected
monotonic clock (``time.monotonic`` by default), read once at the start of
every public call, so a lease is checked against the time of the write itself
rather than a time the caller supplies. Each ``tick()``:

1. reads up to ``max_lines_per_tick`` board lines and keeps the latest valid
   T:1001 feedback (timestamped with that tick's clock reading);
2. marks the link up while that feedback is at most ``link_timeout_s`` old,
   and down (stop, disarm) otherwise;
3. writes the guard's output: a motion command at most once per
   ``send_period_s``; a stop immediately on every transition to stop, then
   again each period while inside the stop-resend window or while fresh
   feedback still shows the tracks moving; nothing after that;
4. polls feedback with ``{"T":130}`` once per ``send_period_s``. Polling (rather
   than the T:131 stream) leaves no board setting behind. It is round-trip
   evidence of link health only while nothing else makes the board print
   T:1001: the T:131 stream (which ``/boot.mission`` may enable) or T:130
   requests from the web UI or ESP-NOW would keep the link looking up while
   the host's own bytes are not arriving. Commissioning checks this.

A clock reading that is not finite or earlier than the previous one latches a
fault: the client writes STOP, disarms and otherwise ignores that call (no
feedback read, no schedule change). Valid readings then resume normally;
motion needs a new ``arm()`` and command.

Transport errors (OSError) mark the link down instead of propagating. After
the link returns, a stop is written at once: stops written while the link was
silently down never reached the board, whose last setpoint runs until its
heartbeat expires (about 3 s, unverified on this robot).

Any byte received from serial start-up until the boot mission ends (several
seconds; longer in Wi-Fi STA mode) aborts that mission, so start the client
only after the board has finished booting.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .guard import DEFAULT_LEASE_S, GuardConfig, MotionGuard, StopReason, SubmitResult
from .protocol import (
    DEFAULT_SPEED_CAP_M_PER_S,
    STOP,
    BaseFeedback,
    FeedbackRequest,
    SourceMode,
    WheelSpeedCommand,
    encode_command,
    parse_feedback_line,
)

if TYPE_CHECKING:  # the client never needs the serial driver at run time
    from .transport import Transport

DEFAULT_SEND_PERIOD_S: Final = 0.1
"""10 Hz: matches the firmware PID's 100 ms sample time; command, poll and echo use ~12 % of 115200 baud."""


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Client limits: speeds in m/s, times in seconds of the client's injected monotonic clock."""

    speed_cap_m_per_s: float = DEFAULT_SPEED_CAP_M_PER_S
    lease_s: float = DEFAULT_LEASE_S
    send_period_s: float = DEFAULT_SEND_PERIOD_S
    link_timeout_s: float = 0.5
    stop_resend_s: float = 1.0
    max_lines_per_tick: int = 50

    def __post_init__(self) -> None:
        if not 0.02 <= self.send_period_s <= 1.0:
            raise ValueError("send_period_s must be in [0.02, 1.0]")
        if not 2 * self.send_period_s <= self.link_timeout_s <= 2.0:
            raise ValueError("link_timeout_s must be in [2 * send_period_s, 2.0]")
        if not 0.0 <= self.stop_resend_s <= 5.0:
            raise ValueError("stop_resend_s must be in [0, 5]")
        if self.max_lines_per_tick < 1:
            raise ValueError("max_lines_per_tick must be positive")
        GuardConfig(lease_s=self.lease_s, speed_cap_m_per_s=self.speed_cap_m_per_s)


@dataclass(frozen=True, slots=True)
class ClientStatus:
    """Snapshot of the client after a call. ``commanded`` is the guard output at the last tick."""

    source: SourceMode
    link_up: bool
    feedback_age_s: float | None
    last_feedback: BaseFeedback | None
    armed: bool
    stop_reason: StopReason | None
    stop_detail: str | None
    commanded: WheelSpeedCommand
    lines_read: int
    invalid_feedback: int
    io_error: str | None


class UGV01Client:
    """Bounded, lease-guarded UGV01 command/feedback loop over a ``Transport``."""

    def __init__(
        self,
        transport: Transport,
        config: ClientConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Drive ``transport``; ``clock`` returns monotonic seconds and is read once per call."""
        self._transport = transport
        self._config = config if config is not None else ClientConfig()
        self._clock = clock
        self._guard = MotionGuard(
            GuardConfig(lease_s=self._config.lease_s, speed_cap_m_per_s=self._config.speed_cap_m_per_s)
        )
        self._last_now_s: float | None = None  # latest valid clock reading
        self._last_feedback: BaseFeedback | None = None
        self._next_send_s: float | None = None
        self._stop_written = False  # last wheel command that reached the transport was STOP
        self._stop_resend_until_s = 0.0
        self._commanded = STOP
        self._lines_read = 0
        self._invalid_feedback = 0
        self._io_error: str | None = None

    def arm(self) -> bool:
        """Allow motion. Refused until fresh valid feedback shows the link is up."""
        now_s = self._now()
        if now_s is None:
            return False
        self._refresh_link(now_s)
        return self._guard.arm(now_s)

    def send_wheel_speeds(self, left_m_per_s: float, right_m_per_s: float) -> SubmitResult:
        """Offer new track speeds (m/s). If accepted, ticks send them until the lease ends."""
        now_s = self._now()
        if now_s is None:
            return SubmitResult.REJECTED_NOT_ARMED
        self._refresh_link(now_s)
        return self._guard.submit(WheelSpeedCommand(left_m_per_s, right_m_per_s), now_s)

    def stop(self) -> None:
        """Disarm and write STOP immediately, bypassing the rate limit."""
        now_s = self._now()
        if now_s is None:
            return  # an invalid reading has already disarmed and written STOP
        self._guard.stop(now_s)
        self._commanded = STOP
        self._write_wheels(STOP, now_s, new_stop=True)

    def tick(self) -> ClientStatus:
        """Read feedback, update link health, and write the guard's output (rate-bounded)."""
        now_s = self._now()
        if now_s is not None:
            self._read_available(now_s)
            self._refresh_link(now_s)
            self._commanded = self._guard.output(now_s)
            self._send(self._commanded, now_s)
        return self._status_at(self._last_now_s)

    def status(self) -> ClientStatus:
        """Current link, guard and I/O state (at the latest valid clock reading)."""
        self._now()
        return self._status_at(self._last_now_s)

    def close(self) -> None:
        """Write STOP, then close the transport."""
        try:
            self.stop()
        finally:
            self._transport.close()

    def _now(self) -> float | None:
        """Read the clock once. An invalid reading latches a fault, writes STOP and returns None.

        The reading is otherwise ignored: no schedule, feedback or stop-tracking
        state is derived from it, so valid time resumes polling normally.
        """
        now_s = self._clock()
        if math.isfinite(now_s) and (self._last_now_s is None or now_s >= self._last_now_s):
            self._last_now_s = now_s
            return now_s
        self._guard.fault(f"invalid clock reading {now_s!r}", self._last_now_s or 0.0)
        self._commanded = STOP
        try:
            self._transport.write_line(encode_command(STOP))
        except OSError as error:
            self._io_error = f"{type(error).__name__}: {error}"
        return None

    def _status_at(self, now_s: float | None) -> ClientStatus:
        return ClientStatus(
            source=self._transport.source_mode,
            link_up=self._guard.link_up,
            feedback_age_s=None if now_s is None else self._feedback_age_s(now_s),
            last_feedback=self._last_feedback,
            armed=self._guard.armed,
            stop_reason=self._guard.stop_reason,
            stop_detail=self._guard.detail,
            commanded=self._commanded,
            lines_read=self._lines_read,
            invalid_feedback=self._invalid_feedback,
            io_error=self._io_error,
        )

    def _read_available(self, now_s: float) -> None:
        for _ in range(self._config.max_lines_per_tick):
            try:
                line = self._transport.read_line(0.0)
            except OSError as error:
                self._link_failed(error, now_s)
                return
            if line is None:
                return
            self._lines_read += 1
            messages = parse_feedback_line(
                line, received_monotonic_s=now_s, source=self._transport.source_mode
            )
            for message in messages:
                if not isinstance(message, BaseFeedback):
                    continue
                if message.valid:
                    self._last_feedback = message
                else:
                    self._invalid_feedback += 1

    def _feedback_age_s(self, now_s: float) -> float | None:
        if self._last_feedback is None:
            return None
        return now_s - self._last_feedback.received_monotonic_s

    def _feedback_fresh(self, now_s: float) -> bool:
        age_s = self._feedback_age_s(now_s)
        return age_s is not None and 0.0 <= age_s <= self._config.link_timeout_s

    def _refresh_link(self, now_s: float) -> None:
        fresh = self._feedback_fresh(now_s)
        if fresh and not self._guard.link_up:
            self._guard.link_restored(now_s)
            self._stop_written = False  # stops sent while the link was down may never have arrived
        elif not fresh and self._guard.link_up:
            self._guard.link_lost(now_s)

    def _link_failed(self, error: OSError, now_s: float) -> None:
        self._io_error = f"{type(error).__name__}: {error}"
        self._last_feedback = None  # the link counts as down until new feedback arrives
        self._stop_written = False
        self._guard.link_lost(now_s)

    def _send(self, output: WheelSpeedCommand, now_s: float) -> None:
        due = self._next_send_s is None or now_s >= self._next_send_s
        if output.is_stop:
            if not self._stop_written:
                self._write_wheels(STOP, now_s, new_stop=True)
            elif due and self._stop_needs_resend(now_s):
                self._write_wheels(STOP, now_s, new_stop=False)
        elif due:
            self._write_wheels(output, now_s, new_stop=False)
        if due:
            self._write(encode_command(FeedbackRequest.BASE), now_s)
            self._next_send_s = now_s + self._config.send_period_s

    def _stop_needs_resend(self, now_s: float) -> bool:
        if now_s < self._stop_resend_until_s:
            return True
        feedback = self._last_feedback
        return feedback is not None and self._feedback_fresh(now_s) and not feedback.stationary

    def _write_wheels(self, command: WheelSpeedCommand, now_s: float, *, new_stop: bool) -> None:
        line = encode_command(command, speed_cap_m_per_s=self._config.speed_cap_m_per_s)
        if not self._write(line, now_s):
            return
        if command.is_stop:
            if new_stop:
                self._stop_resend_until_s = now_s + self._config.stop_resend_s
            self._stop_written = True
        else:
            self._stop_written = False

    def _write(self, line: bytes, now_s: float) -> bool:
        try:
            self._transport.write_line(line)
        except OSError as error:
            self._link_failed(error, now_s)
            return False
        return True
