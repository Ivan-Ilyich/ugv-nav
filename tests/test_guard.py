"""Control-boundary tests for the motion guard (lease, stop priority, re-arm)."""

from __future__ import annotations

import math

import pytest

from ugv_nav.ugv01.guard import GuardConfig, MotionGuard, StopReason, SubmitResult
from ugv_nav.ugv01.protocol import STOP, WheelSpeedCommand

FORWARD = WheelSpeedCommand(0.08, 0.08)
TURN = WheelSpeedCommand(-0.05, 0.05)


def armed_guard(now_s: float = 0.0, lease_s: float = 0.5) -> MotionGuard:
    guard = MotionGuard(GuardConfig(lease_s=lease_s))
    guard.link_restored(now_s)
    assert guard.arm(now_s)
    return guard


def test_starts_stopped_and_needs_link_and_arm_before_any_command() -> None:
    guard = MotionGuard()
    assert guard.output(0.0) == STOP
    assert guard.submit(FORWARD, 0.0) is SubmitResult.REJECTED_NOT_ARMED
    assert not guard.arm(0.0)  # no evidence of a live link yet
    guard.link_restored(0.1)
    assert guard.arm(0.1)
    assert guard.output(0.1) == STOP  # armed, but nothing commanded yet


def test_command_holds_only_until_its_lease_expires_then_requires_rearm() -> None:
    guard = armed_guard(lease_s=0.5)
    assert guard.submit(FORWARD, 1.0) is SubmitResult.ACCEPTED
    assert guard.output(1.499) == FORWARD
    assert guard.output(1.5) == STOP
    assert guard.stop_reason is StopReason.LEASE_EXPIRED
    assert guard.submit(FORWARD, 1.6) is SubmitResult.REJECTED_NOT_ARMED
    assert guard.arm(1.7)
    assert guard.output(1.7) == STOP  # the expired command does not come back


def test_each_accepted_command_starts_a_new_lease() -> None:
    guard = armed_guard(lease_s=0.5)
    guard.submit(FORWARD, 0.0)
    guard.submit(TURN, 0.4)
    assert guard.output(0.8) == TURN
    assert guard.output(0.9) == STOP


def test_late_command_after_expiry_is_rejected_even_without_output_calls() -> None:
    guard = armed_guard(lease_s=0.5)
    guard.submit(FORWARD, 0.0)
    assert guard.submit(FORWARD, 0.6) is SubmitResult.REJECTED_NOT_ARMED
    assert guard.output(0.6) == STOP


def test_stop_has_priority_and_requires_rearm_and_a_new_command() -> None:
    guard = armed_guard()
    guard.submit(FORWARD, 0.0)
    guard.stop(0.1)
    assert guard.output(0.1) == STOP
    assert guard.stop_reason is StopReason.STOP_REQUESTED
    assert guard.submit(FORWARD, 0.1) is SubmitResult.REJECTED_NOT_ARMED
    assert guard.arm(0.2)
    assert guard.output(0.2) == STOP
    assert guard.submit(TURN, 0.3) is SubmitResult.ACCEPTED
    assert guard.output(0.3) == TURN


@pytest.mark.parametrize(
    "bad",
    [
        WheelSpeedCommand(math.nan, 0.0),
        WheelSpeedCommand(0.0, math.inf),
        WheelSpeedCommand(0.2, 0.0),
        WheelSpeedCommand(0.0, -0.11),
    ],
)
def test_invalid_command_is_rejected_not_clamped_and_stops_the_previous_one(bad: WheelSpeedCommand) -> None:
    guard = armed_guard()
    guard.submit(FORWARD, 0.0)
    assert guard.submit(bad, 0.1) is SubmitResult.REJECTED_INVALID
    assert guard.output(0.1) == STOP
    assert guard.stop_reason is StopReason.INVALID_COMMAND
    assert guard.submit(FORWARD, 0.2) is SubmitResult.REJECTED_NOT_ARMED


def test_fault_stops_and_requires_rearm() -> None:
    guard = armed_guard()
    guard.submit(FORWARD, 0.0)
    guard.fault("operator button", 0.1)
    assert guard.output(0.1) == STOP
    assert (guard.stop_reason, guard.detail) == (StopReason.FAULT, "operator button")
    assert guard.submit(FORWARD, 0.2) is SubmitResult.REJECTED_NOT_ARMED
    assert guard.arm(0.3) and guard.output(0.3) == STOP


def test_link_loss_stops_and_reconnect_never_resumes_the_stale_command() -> None:
    guard = armed_guard()
    guard.submit(FORWARD, 0.0)
    guard.link_lost(0.1)
    assert guard.output(0.1) == STOP
    assert guard.stop_reason is StopReason.LINK_LOST
    assert not guard.arm(0.2)  # cannot arm while the link is down
    guard.link_restored(0.3)
    assert guard.output(0.3) == STOP  # still inside the old lease, still stopped
    assert guard.arm(0.3)
    assert guard.output(0.35) == STOP
    assert guard.submit(TURN, 0.4) is SubmitResult.ACCEPTED
    assert guard.output(0.4) == TURN


def test_clock_running_backwards_stops_and_blocks_arming() -> None:
    guard = armed_guard()
    guard.submit(FORWARD, 1.0)
    assert guard.output(0.9) == STOP
    assert guard.stop_reason is StopReason.CLOCK_ERROR
    assert not guard.arm(0.95)  # still earlier than the latest time seen
    assert guard.arm(1.1)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_time_stops_and_blocks_arming_until_valid_time(bad: float) -> None:
    guard = armed_guard(1.0)
    guard.submit(FORWARD, 1.0)
    assert guard.output(bad) == STOP
    assert guard.stop_reason is StopReason.CLOCK_ERROR
    assert guard.submit(FORWARD, bad) is SubmitResult.REJECTED_NOT_ARMED
    assert not guard.arm(bad)
    assert guard.stop_reason is StopReason.CLOCK_ERROR
    assert guard.arm(1.1)
    assert guard.output(1.1) == STOP  # the old command does not come back


@pytest.mark.parametrize("lease_s", [0.0, 0.01, 1.5, math.nan])
def test_lease_length_is_bounded(lease_s: float) -> None:
    with pytest.raises(ValueError):
        GuardConfig(lease_s=lease_s)
