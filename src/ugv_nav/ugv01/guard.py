"""Pure motion guard: a finite command lease with stop priority and explicit re-arm.

The guard decides what the robot should be commanded *now*. It holds at most
one accepted wheel-speed command, valid only until its lease deadline
(``accepted_at + lease_s``, on the caller's monotonic clock). It outputs
``STOP`` whenever it is not armed, has no command, or the lease has run out.

Stopping events (lease expiry, explicit stop, fault, invalid command, link
loss, a clock that runs backwards) all disarm the guard and discard the held
command. Motion needs an explicit ``arm()`` followed by a *new* command, so a
command from before a stop or reconnect can never resume.

Time is injected as ``now_s`` (seconds from any monotonic clock); the guard
never sleeps or reads a clock itself. It only shapes host output: stopping
after a host crash relies on the firmware heartbeat (about 3 s), which is
unverified on this robot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

from .protocol import (
    DEFAULT_SPEED_CAP_M_PER_S,
    STOP,
    WheelSpeedCommand,
    check_speed_cap,
    wheel_speed_problem,
)

MIN_LEASE_S: Final = 0.05
MAX_LEASE_S: Final = 1.0
DEFAULT_LEASE_S: Final = 0.5
"""Default lease: at the 0.10 m/s default cap a stale command moves the robot at most 5 cm."""


class StopReason(Enum):
    """Why the guard is currently outputting stop and refusing commands."""

    NOT_ARMED = "not_armed"  # initial state
    STOP_REQUESTED = "stop_requested"
    LEASE_EXPIRED = "lease_expired"
    LINK_LOST = "link_lost"
    INVALID_COMMAND = "invalid_command"
    FAULT = "fault"
    CLOCK_ERROR = "clock_error"


class SubmitResult(Enum):
    """Outcome of ``MotionGuard.submit``."""

    ACCEPTED = "accepted"
    REJECTED_NOT_ARMED = "rejected_not_armed"
    REJECTED_INVALID = "rejected_invalid"


@dataclass(frozen=True, slots=True)
class GuardConfig:
    """Guard limits: ``lease_s`` in [MIN_LEASE_S, MAX_LEASE_S]; speed cap as in ``check_speed_cap``."""

    lease_s: float = DEFAULT_LEASE_S
    speed_cap_m_per_s: float = DEFAULT_SPEED_CAP_M_PER_S

    def __post_init__(self) -> None:
        if not MIN_LEASE_S <= self.lease_s <= MAX_LEASE_S:
            raise ValueError(f"lease_s must be in [{MIN_LEASE_S}, {MAX_LEASE_S}] s, got {self.lease_s!r}")
        check_speed_cap(self.speed_cap_m_per_s)


class MotionGuard:
    """Finite-lease motion gate. Starts disarmed with the link marked down."""

    def __init__(self, config: GuardConfig | None = None) -> None:
        self._config = config if config is not None else GuardConfig()
        self._armed = False
        self._stop_reason: StopReason | None = StopReason.NOT_ARMED
        self._detail: str | None = None
        self._command: WheelSpeedCommand | None = None
        self._deadline_s: float | None = None
        self._link_up = False
        self._latest_now_s: float | None = None

    @property
    def config(self) -> GuardConfig:
        """The limits this guard enforces."""
        return self._config

    @property
    def armed(self) -> bool:
        """True while commands are accepted."""
        return self._armed

    @property
    def stop_reason(self) -> StopReason | None:
        """Why the guard is disarmed, or None while armed."""
        return self._stop_reason

    @property
    def detail(self) -> str | None:
        """Free-text detail for the last fault or rejected command."""
        return self._detail

    @property
    def link_up(self) -> bool:
        """Link state last reported by the caller."""
        return self._link_up

    def arm(self, now_s: float) -> bool:
        """Allow new commands. Refused while the link is down or after a clock error.

        Arming never restores an earlier command: output stays stop until a new
        command is submitted. Arming an already armed guard changes nothing.
        """
        if not self._advance(now_s) or not self._link_up:
            return False
        if not self._armed:
            self._armed = True
            self._stop_reason = None
            self._detail = None
        return True

    def submit(self, command: WheelSpeedCommand, now_s: float) -> SubmitResult:
        """Offer a command; if armed and valid it holds until ``now_s + lease_s``.

        An invalid command (non-finite, or above the speed cap) is not clamped:
        it is rejected, and the guard disarms as for a fault.
        """
        if not self._advance(now_s) or not self._armed:
            return SubmitResult.REJECTED_NOT_ARMED
        problem = wheel_speed_problem(command, self._config.speed_cap_m_per_s)
        if problem is not None:
            self._disarm(StopReason.INVALID_COMMAND, problem)
            return SubmitResult.REJECTED_INVALID
        self._command = command
        self._deadline_s = now_s + self._config.lease_s
        return SubmitResult.ACCEPTED

    def stop(self, now_s: float) -> None:
        """Stop now and require re-arm. Takes effect whatever the clock says."""
        self._advance(now_s)
        self._disarm(StopReason.STOP_REQUESTED)

    def fault(self, detail: str, now_s: float) -> None:
        """Latch a fault: stop now and require re-arm."""
        self._advance(now_s)
        self._disarm(StopReason.FAULT, detail)

    def link_lost(self, now_s: float) -> None:
        """Mark the link down: stop now, discard the command, refuse arming until restored."""
        self._advance(now_s)
        self._link_up = False
        self._disarm(StopReason.LINK_LOST)

    def link_restored(self, now_s: float) -> None:
        """Mark the link healthy. Does not arm and restores no command."""
        self._advance(now_s)
        self._link_up = True

    def output(self, now_s: float) -> WheelSpeedCommand:
        """Return the command to send now: the held command within its lease, otherwise ``STOP``."""
        if not self._advance(now_s) or not self._armed or self._command is None:
            return STOP
        return self._command

    def _advance(self, now_s: float) -> bool:
        """Record ``now_s`` and expire the lease. Returns False (and disarms) for invalid time."""
        if not math.isfinite(now_s) or (self._latest_now_s is not None and now_s < self._latest_now_s):
            self._disarm(StopReason.CLOCK_ERROR, f"invalid time {now_s!r} (latest was {self._latest_now_s!r})")
            return False
        self._latest_now_s = now_s
        if self._deadline_s is not None and now_s >= self._deadline_s:
            self._disarm(StopReason.LEASE_EXPIRED)
        return True

    def _disarm(self, reason: StopReason, detail: str | None = None) -> None:
        self._armed = False
        self._stop_reason = reason
        self._detail = detail
        self._command = None
        self._deadline_s = None
