"""End-to-end tests: UGV01Client against SimulatedUGV01 (no hardware involved)."""

from __future__ import annotations

import math
import subprocess
import sys
from typing import Any

import pytest

from ugv_nav.ugv01.client import ClientConfig, ClientStatus, UGV01Client
from ugv_nav.ugv01.guard import StopReason, SubmitResult
from ugv_nav.ugv01.protocol import STOP, FeedbackRequest, SourceMode, encode_command
from ugv_nav.ugv01.sim import ManualClock, SimulatedUGV01

TICK_S = 0.02  # the caller's loop; the client itself writes at most every 0.1 s
STOPPED = (0.0, 0.0)
STOP_LINE = encode_command(STOP)
POLL_LINE = encode_command(FeedbackRequest.BASE)


class Rig:
    """Client + simulated board sharing one manual clock."""

    def __init__(self, config: ClientConfig | None = None) -> None:
        self.clock = ManualClock(100.0)
        self.sim = SimulatedUGV01(self.clock)
        self.client = UGV01Client(self.sim, config, clock=self.clock)

    def now(self) -> float:
        return self.clock()

    def run(self, duration_s: float, *, planner: tuple[float, float] | None = None) -> ClientStatus:
        """Tick for ``duration_s``; ``planner`` resubmits these speeds before every tick."""
        end_s = self.now() + duration_s
        status = self.client.status()
        while self.now() < end_s - 1e-9:
            self.clock.advance(TICK_S)
            if planner is not None:
                self.client.send_wheel_speeds(*planner)
            status = self.client.tick()
        return status

    def start_moving(self, left_m_per_s: float, right_m_per_s: float) -> None:
        self.run(0.3)  # polled feedback brings the link up
        assert self.client.arm()
        result = self.client.send_wheel_speeds(left_m_per_s, right_m_per_s)
        assert result is SubmitResult.ACCEPTED
        self.run(0.3, planner=(left_m_per_s, right_m_per_s))
        assert self.sim.track_speeds_m_per_s() == (left_m_per_s, right_m_per_s)

    def motion_received_since(self, index: int) -> list[tuple[float, float]]:
        return [(event.left_m_per_s, event.right_m_per_s) for event in self.sim.motion_log[index:]]


def test_motion_follows_guard_and_lease_expiry_stops_before_the_firmware_heartbeat() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.06)
    status = rig.run(1.0, planner=(0.08, 0.06))
    assert status.link_up and status.armed and status.source == "simulation"
    assert status.last_feedback is not None and status.last_feedback.left_m_per_s == 0.08
    rig.run(0.4)  # planner falls silent; the 0.5 s lease is still running
    assert rig.sim.track_speeds_m_per_s() == (0.08, 0.06)
    status = rig.run(0.15)
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    assert status.stop_reason is StopReason.LEASE_EXPIRED
    assert rig.sim.heartbeat_stops == 0


def test_motion_writes_are_rate_bounded_however_fast_the_caller_ticks() -> None:
    rig = Rig()
    rig.start_moving(0.05, 0.05)
    first = len(rig.sim.motion_log)
    for _ in range(1000):  # 1 s at 1 kHz with a fresh command every tick
        rig.clock.advance(0.001)
        rig.client.send_wheel_speeds(0.05, 0.05)
        rig.client.tick()
    assert 9 <= len(rig.motion_received_since(first)) <= 11


def test_explicit_stop_is_written_at_once_resent_for_a_bounded_window_then_quiet() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    rig.client.stop()
    assert rig.sim.track_speeds_m_per_s() == STOPPED  # no tick needed
    assert rig.client.send_wheel_speeds(0.08, 0.08) is SubmitResult.REJECTED_NOT_ARMED
    first = len(rig.sim.motion_log) - 1
    rig.run(1.5)
    stops = rig.motion_received_since(first)
    assert set(stops) == {STOPPED} and 8 <= len(stops) <= 12
    quiet_from = len(rig.sim.motion_log)
    status = rig.run(3.0)
    assert rig.motion_received_since(quiet_from) == []  # nothing keeps refreshing the heartbeat
    assert status.link_up  # feedback polling continues


def test_a_late_tick_writes_stop_because_the_lease_is_checked_on_the_client_clock() -> None:
    config = ClientConfig(link_timeout_s=2.0)  # so that only the lease can stop the command
    rig = Rig(config)
    rig.start_moving(0.08, 0.08)
    assert rig.client.send_wheel_speeds(0.08, 0.08) is SubmitResult.ACCEPTED
    deadline_s = rig.now() + config.lease_s
    rig.clock.advance(1.5)  # the caller stalls: no ticks until well after the lease
    status = rig.client.tick()
    late = [(e.left_m_per_s, e.right_m_per_s) for e in rig.sim.motion_log if e.time_s >= deadline_s]
    assert late and set(late) == {STOPPED}
    assert status.link_up and status.stop_reason is StopReason.LEASE_EXPIRED


class FaultyClock:
    """Reads a ManualClock, except that ``reading`` is returned instead while it is set."""

    def __init__(self, clock: ManualClock) -> None:
        self.clock = clock
        self.reading: float | None = None

    def __call__(self) -> float:
        return self.clock() if self.reading is None else self.reading


def test_invalid_clock_readings_write_stop_and_disarm_without_wedging_the_poll() -> None:
    rig = Rig()
    clock = FaultyClock(rig.clock)
    rig.client = UGV01Client(rig.sim, clock=clock)
    rig.start_moving(0.08, 0.08)
    for reading in (math.inf, math.nan):
        clock.reading = reading
        rig.clock.advance(0.5)  # real time passes while the clock misreads
        written = len(rig.sim.host_lines)
        status = rig.client.tick()
        assert rig.sim.host_lines[written:] == [STOP_LINE]
        assert not status.armed and status.stop_reason is StopReason.FAULT
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    clock.reading = None
    written = len(rig.sim.host_lines)
    status = rig.run(0.3)
    assert status.link_up and rig.sim.host_lines[written:].count(POLL_LINE) >= 2
    status = rig.run(1.0)  # longer than link_timeout_s: only fresh polls keep the link up
    assert status.link_up and not status.armed
    assert rig.client.arm()


def test_invalid_speed_is_rejected_and_the_next_tick_writes_stop() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    assert rig.client.send_wheel_speeds(math.nan, 0.0) is SubmitResult.REJECTED_INVALID
    first = len(rig.sim.motion_log)
    rig.clock.advance(TICK_S)
    status = rig.client.tick()
    assert rig.motion_received_since(first) == [STOPPED]
    assert status.stop_reason is StopReason.INVALID_COMMAND


@pytest.mark.parametrize(
    "limits", [{"send_period_s": math.nan}, {"link_timeout_s": 0.1}, {"stop_resend_s": math.nan}]
)
def test_client_limits_are_bounded(limits: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ClientConfig(**limits)


def test_stop_on_a_failed_transport_records_the_error_without_raising() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    rig.sim.set_disconnected(True)
    rig.client.stop()
    status = rig.client.status()
    assert status.io_error is not None and not status.armed


@pytest.mark.parametrize("value", [math.nan, math.inf, -0.1])
def test_manual_clock_refuses_time_that_is_not_finite_or_runs_backwards(value: float) -> None:
    clock = ManualClock(1.0)
    with pytest.raises(ValueError):
        clock.advance(value)
    assert clock() == 1.0
    if not math.isfinite(value):
        with pytest.raises(ValueError):
            ManualClock(value)


def test_simulated_heartbeat_is_refreshed_only_by_motion_commands() -> None:
    clock = ManualClock()
    sim = SimulatedUGV01(clock)
    sim.write_line(b'{"T":1,"L":0.1,"R":0.1}\n')
    for _ in range(29):
        clock.advance(0.1)
        sim.write_line(b'{"T":130}\n')  # polling does not keep the robot moving
    clock.advance(0.05)
    assert sim.track_speeds_m_per_s() == (0.1, 0.1)
    clock.advance(0.1)
    assert sim.track_speeds_m_per_s() == STOPPED
    sim.write_line(b'{"T":1,"L":0.1,"R":0.1}\n')
    clock.advance(2.0)
    sim.write_line(b'{"T":1,"L":3.0,"R":3.0}\n')  # ignored as out of range, yet refreshes the heartbeat
    clock.advance(2.0)
    assert sim.track_speeds_m_per_s() == (0.1, 0.1)
    assert sim.motion_log[-1].applied is False


def test_silent_link_loss_stops_and_reconnect_sends_stop_never_stale_motion() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    rig.sim.set_link_up(False)  # cut wire: no errors, just silence
    status = rig.run(1.0, planner=(0.08, 0.08))
    assert not status.link_up and not status.armed
    assert status.stop_reason is StopReason.LINK_LOST
    assert rig.sim.track_speeds_m_per_s() == (0.08, 0.08)  # the board never heard the stop
    first = len(rig.sim.motion_log)
    rig.sim.set_link_up(True)
    status = rig.run(1.0, planner=(0.08, 0.08))  # planner still asking for the old speeds
    assert status.link_up and not status.armed
    received = rig.motion_received_since(first)
    assert received and set(received) == {STOPPED}
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    assert rig.sim.heartbeat_stops == 0  # the host's stop arrived first
    assert rig.client.arm()
    assert rig.client.send_wheel_speeds(0.03, 0.03) is SubmitResult.ACCEPTED
    rig.run(0.3, planner=(0.03, 0.03))
    assert rig.sim.track_speeds_m_per_s() == (0.03, 0.03)


def test_transport_errors_mark_the_link_down_without_raising() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    rig.sim.set_disconnected(True)  # unplugged adapter: every I/O call raises
    status = rig.run(0.5, planner=(0.08, 0.08))
    assert not status.link_up and not status.armed and status.io_error is not None
    rig.sim.set_disconnected(False)
    status = rig.run(0.5, planner=(0.08, 0.08))
    assert status.link_up and not status.armed
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_malformed_board_output_is_tolerated() -> None:
    rig = Rig()
    rig.run(0.3)
    rig.sim.inject_output(b"\xff\x00garbage\r\n" + b'{"T":1001,"L":0.1\r\n' + b"[missionPlay finished.]\r\n")
    rig.sim.inject_output(b'{"T":1001,"L":"x","R":0}\r\n')
    rig.sim.inject_output(b'{"ip":"192.0.2.7","rssi":-40}')  # no newline: glued to the next reply
    status = rig.run(0.3)
    assert status.link_up and status.last_feedback is not None and status.last_feedback.valid
    assert status.invalid_feedback == 1
    assert rig.client.arm()


class InvalidFeedbackBoard:
    """A board whose every T:1001 is invalid (here: PWM counts instead of m/s)."""

    source_mode: SourceMode = "simulation"

    def __init__(self) -> None:
        self.pending: list[bytes] = []

    def write_line(self, line: bytes) -> None:
        if line == b'{"T":130}\n':
            self.pending.append(b'{"T":1001,"L":255,"R":255}')

    def read_line(self, timeout_s: float) -> bytes | None:
        return self.pending.pop(0) if self.pending else None

    def close(self) -> None:
        pass


def test_invalid_feedback_does_not_count_as_a_live_link() -> None:
    board = InvalidFeedbackBoard()
    clock = ManualClock()
    client = UGV01Client(board, clock=clock)
    status = client.tick()
    for _ in range(19):
        clock.advance(0.1)
        status = client.tick()
    assert status.invalid_feedback >= 10
    clock.advance(0.1)
    assert not status.link_up and not client.arm()


def test_close_writes_stop_then_closes() -> None:
    rig = Rig()
    rig.start_moving(0.08, 0.08)
    rig.client.close()
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    rig.clock.advance(0.1)
    assert rig.client.tick().io_error is not None


def test_simulation_path_does_not_load_the_serial_driver() -> None:
    code = "import sys, ugv_nav.ugv01.client, ugv_nav.ugv01.sim; sys.exit('serial' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
