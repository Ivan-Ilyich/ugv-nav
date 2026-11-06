"""Control-boundary tests for tools/ugv01_drive_check.py.

The whole stack runs as on the robot (tool, client, guard, HttpTransport), with
GETs answered by the simulator on a manual clock. Nothing here touches hardware.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import itertools
import json
import os
import subprocess
import sys
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

import ugv_nav.ugv01.client as client_module
from ugv_nav.ugv01.client import UGV01Client
from ugv_nav.ugv01.protocol import (
    DEFAULT_SPEED_CAP_M_PER_S,
    FIRMWARE_HEARTBEAT_TIMEOUT_S,
    STOP,
    Command,
    FeedbackRequest,
    WheelSpeedCommand,
    encode_command,
)
from ugv_nav.ugv01.sim import ManualClock, SimulatedUGV01
from ugv_nav.ugv01.transport import HttpTransport

REPO = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO / "tools" / "ugv01_drive_check.py"
STOP_LINE = encode_command(STOP)
POLL_LINE = encode_command(FeedbackRequest.BASE)
STOPPED = (0.0, 0.0)
ALL_CONFIRMED = ("go a", "go b", "go c")
INTERRUPT_AFTER_WAITS = 30  # 0.3 s into a phase: motion is on the wire, and every phase lasts longer


def load_tool() -> ModuleType:
    """Import the tool as a module (tools/ is not a package)."""
    spec = importlib.util.spec_from_file_location("ugv01_drive_check", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


drive = load_tool()


class Rig:
    """The tool's full stack, with the simulated board behind HttpTransport and a scripted operator."""

    def __init__(
        self,
        answers: tuple[str, ...] = ALL_CONFIRMED,
        *,
        heartbeat_timeout_s: float = FIRMWARE_HEARTBEAT_TIMEOUT_S,
    ) -> None:
        self.clock = ManualClock(100.0)
        self.sim = SimulatedUGV01(self.clock, heartbeat_timeout_s=heartbeat_timeout_s, echo=False)
        self.answers = list(answers)
        self.waited_s = 0.0
        self.interrupts: list[tuple[str, str]] = []
        """(step, phase) pairs: raise KeyboardInterrupt ``INTERRUPT_AFTER_WAITS`` waits into each, in order."""
        self.waits_in_phase = 0
        self.interrupted_at: int | None = None
        """Number of requests served when the last interrupt fired."""
        self.speeds_at_interrupt: tuple[float, float] | None = None
        self.before_request: Callable[[bytes], None] | None = None
        self.reply_filter: Callable[[bytes], bytes] | None = None
        self.requests: list[tuple[float, bytes]] = []
        self.csv = io.StringIO()
        self.recorder = drive.RecordingTransport(HttpTransport("192.0.2.7", get=self.get), self.csv, self.clock)
        self.client = UGV01Client(self.recorder, drive.CLIENT_CONFIG, clock=self.clock)
        self.check = drive.DriveCheck(
            self.client, self.recorder, read_typed=self.read_typed, sleep=self.sleep, clock=self.clock
        )

    def get(self, url: str, timeout_s: float) -> bytes:
        """Answer one GET like the firmware's /js handler."""
        line = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["json"][0].encode("ascii") + b"\n"
        if self.before_request is not None:
            self.before_request(line)
        self.requests.append((self.clock(), line))
        self.sim.write_line(line)
        reply = self.sim.read_line(0.0)
        if reply is None:
            return b"null"
        return reply if self.reply_filter is None else self.reply_filter(reply)

    def sleep(self, duration_s: float) -> None:
        self.clock.advance(duration_s)
        self.maybe_interrupt()

    def read_typed(self, timeout_s: float) -> str | None:
        """The operator takes 0.5 s per prompt; "" (end of input) once out of answers."""
        self.clock.advance(timeout_s)
        self.maybe_interrupt()
        self.waited_s += timeout_s
        if self.waited_s < 0.5:
            return None
        self.waited_s = 0.0
        return self.answers.pop(0) + "\n" if self.answers else ""

    def maybe_interrupt(self) -> None:
        if not self.interrupts or self.interrupts[0] != (self.recorder.step, self.recorder.phase):
            return
        self.waits_in_phase += 1
        if self.waits_in_phase >= INTERRUPT_AFTER_WAITS:
            self.waits_in_phase = 0
            self.interrupts.pop(0)
            self.interrupted_at = len(self.requests)
            self.speeds_at_interrupt = self.sim.track_speeds_m_per_s()
            raise KeyboardInterrupt

    def run(self) -> bool:
        passed: bool = drive.run_drive_check(self.check)
        return passed

    def wheel_lines_since(self, index: int) -> list[bytes]:
        return [line for _, line in self.requests[index:] if line != POLL_LINE]

    def motion_times(self) -> list[float]:
        return [e.time_s for e in self.sim.motion_log if (e.left_m_per_s, e.right_m_per_s) != STOPPED]

    def result(self, step: str) -> object:
        return next(result for result in self.check.results if result.step == step)


def sample(t_s: float, speed_m_per_s: float) -> object:
    return drive.Sample(t_s, speed_m_per_s, speed_m_per_s)


# --- Each step stops -------------------------------------------------------------


def test_full_run_passes_and_every_step_measures_a_stop() -> None:
    rig = Rig()
    assert rig.run()
    assert [result.step for result in rig.check.results] == ["a", "b", "c"]
    assert all(result.problem is None for result in rig.check.results)
    assert all(result.peak_left_m_per_s == drive.DRIVE_SPEED_M_PER_S for result in rig.check.results)
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    assert rig.wheel_lines_since(0)[-1] == STOP_LINE


def test_step_a_stops_from_the_host_at_the_end_of_the_drive() -> None:
    rig = Rig(("go a",))
    rig.run()
    first_t1_s = rig.motion_times()[0]
    stop_s = rig.recorder.first_stop_write_since(first_t1_s)
    assert stop_s - first_t1_s == pytest.approx(drive.DRIVE_S, abs=0.03)
    assert rig.sim.heartbeat_stops == 0
    assert rig.check.results[0].time_to_still_s <= 0.15  # the simulator stops instantly: one poll


def test_step_b_writes_no_stop_until_the_lease_ends_and_the_guard_says_so() -> None:
    rig = Rig(("go a", "go b"))
    rig.run()
    result = rig.check.results[1]
    assert result.problem is None  # the guard reported LEASE_EXPIRED
    assert rig.sim.heartbeat_stops == 0
    motion = rig.motion_times()
    second_drive_s = next(later for earlier, later in itertools.pairwise(motion) if later - earlier > 1.0)
    stop_s = rig.recorder.first_stop_write_since(second_drive_s)
    assert stop_s > motion[-1]  # nothing was stopped early: every T:1 of the drive came first
    assert stop_s - second_drive_s == pytest.approx(drive.DRIVE_S + drive.DEFAULT_LEASE_S, abs=0.03)


def test_step_c_sends_only_polls_until_the_firmware_heartbeat_has_stopped_the_tracks() -> None:
    rig = Rig()
    rig.run()
    last_t1_s = rig.motion_times()[-1]
    window = [line for t_s, line in rig.requests if last_t1_s < t_s < last_t1_s + drive.HEARTBEAT_WATCH_S]
    assert window and set(window) == {POLL_LINE}
    assert rig.sim.heartbeat_stops == 1
    result = rig.check.results[2]
    assert 3.0 <= result.time_to_still_s <= 3.2


def test_step_c_host_stops_and_reports_failure_if_the_heartbeat_never_fires() -> None:
    rig = Rig(heartbeat_timeout_s=1000.0)
    assert not rig.run()
    result = rig.check.results[2]
    assert result.time_to_still_s is None and "did not read still" in result.problem
    assert rig.sim.heartbeat_stops == 0
    assert rig.sim.track_speeds_m_per_s() == STOPPED  # only the host's STOP can have done this
    stop_s = next(t_s for t_s, line in rig.requests if line == STOP_LINE and t_s > rig.motion_times()[-1])
    assert stop_s - rig.motion_times()[-1] == pytest.approx(drive.HEARTBEAT_WATCH_S, abs=0.05)


def test_a_step_that_never_moves_is_a_failure_not_an_instant_stop() -> None:
    rig = Rig()
    rig.reply_filter = lambda reply: b'{"T":1001,"L":0,"R":0,"r":0,"p":0,"v":11.7}'
    assert not rig.run()
    assert len(rig.check.results) == 1 and "never read as moving" in rig.check.results[0].problem
    assert rig.answers == ["go b", "go c"]  # the run ended without offering step b


def test_tracks_already_moving_refuse_to_arm() -> None:
    rig = Rig()
    rig.reply_filter = lambda reply: b'{"T":1001,"L":0.05,"R":0.05,"r":0,"p":0,"v":11.7}'
    assert not rig.run()
    assert rig.motion_times() == [] and rig.check.results == []


def test_link_failure_during_the_drive_aborts_and_the_stop_is_retried() -> None:
    rig = Rig()
    failures = 3

    def fail_after_motion_starts(line: bytes) -> None:
        nonlocal failures
        if rig.recorder.phase == "drive" and rig.motion_times() and failures > 0:
            failures -= 1
            raise TimeoutError("timed out")

    rig.before_request = fail_after_motion_starts
    assert not rig.run()
    assert rig.check.results == []
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    assert rig.wheel_lines_since(0)[-1] == STOP_LINE


# --- Typed confirmation ----------------------------------------------------------


@pytest.mark.parametrize("answer", ["", "y", "yes", "go", "go b", "GO A"])
def test_nothing_moves_without_the_exact_phrase(answer: str) -> None:
    rig = Rig((answer,))
    assert not rig.run()
    assert rig.motion_times() == []


def test_each_step_needs_its_own_confirmation() -> None:
    rig = Rig(("go a", "no"))
    assert not rig.run()
    assert [result.step for result in rig.check.results] == ["a"]
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_end_of_input_counts_as_no() -> None:
    rig = Rig(())
    assert not rig.run()
    assert rig.motion_times() == []


def test_read_typed_returns_a_typed_line_and_times_out_without_one(monkeypatch: pytest.MonkeyPatch) -> None:
    read_end, write_end = os.pipe()
    with os.fdopen(read_end) as stdin, os.fdopen(write_end, "w") as typed:
        monkeypatch.setattr(sys, "stdin", stdin)
        assert drive.read_typed(0.0) is None
        typed.write("go a\n")
        typed.flush()
        assert drive.read_typed(1.0) == "go a\n"


# --- Choosing steps --------------------------------------------------------------


def test_a_single_step_can_be_run_alone_and_passes_on_its_own() -> None:
    rig = Rig(("go c",))
    assert drive.run_drive_check(rig.check, drive.selected_steps("c"))
    assert [result.step for result in rig.check.results] == ["c"]
    assert rig.sim.heartbeat_stops == 1
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_a_chosen_step_still_needs_its_own_phrase() -> None:
    rig = Rig(("go a",))
    assert not drive.run_drive_check(rig.check, drive.selected_steps("c"))
    assert rig.motion_times() == []


def test_chosen_steps_keep_their_order_and_all_must_pass() -> None:
    assert [step.letter for step in drive.selected_steps("ca")] == ["a", "c"]
    rig = Rig(("go a", "no"))
    assert not drive.run_drive_check(rig.check, drive.selected_steps("ca"))
    assert [result.step for result in rig.check.results] == ["a"]


@pytest.mark.parametrize("text", ["", "d", "ad", "C"])
def test_unknown_steps_are_refused(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        drive.selected_steps(text)


# --- Ctrl+C ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("where", "moving"),
    [
        (("a", "idle"), False),
        (("a", "drive"), True),
        (("a", "observe"), False),
        (("b", "drive"), True),
        (("b", "lease_running"), True),
        (("c", "idle"), False),
        (("c", "drive"), True),
        (("c", "silent"), True),
        (("c", "host_stop_after_watch"), False),
    ],
)
def test_ctrl_c_sends_stop_wherever_it_lands(where: tuple[str, str], moving: bool) -> None:
    rig = Rig()
    rig.interrupts = [where]
    assert not rig.run()
    assert rig.interrupted_at is not None
    assert (rig.speeds_at_interrupt != STOPPED) is moving  # otherwise this case proves nothing
    after = rig.wheel_lines_since(rig.interrupted_at)
    assert after and set(after) == {STOP_LINE}  # the very next wheel line is STOP, and no motion follows
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_ctrl_c_during_the_silent_step_beats_the_heartbeat() -> None:
    rig = Rig()
    rig.interrupts = [("c", "silent")]
    rig.run()
    assert rig.sim.heartbeat_stops == 0
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_ctrl_c_inside_an_http_request_sends_stop() -> None:
    rig = Rig()
    pressed = False

    def press_during_a_motion_write(line: bytes) -> None:
        nonlocal pressed
        if not pressed and line not in (POLL_LINE, STOP_LINE):
            pressed = True
            rig.interrupted_at = len(rig.requests)
            raise KeyboardInterrupt

    rig.before_request = press_during_a_motion_write
    assert not rig.run()
    assert set(rig.wheel_lines_since(rig.interrupted_at or 0)) == {STOP_LINE}
    assert rig.sim.track_speeds_m_per_s() == STOPPED


def test_a_second_ctrl_c_cannot_cut_the_stop_short() -> None:
    rig = Rig()
    rig.interrupts = [("a", "drive"), ("a", "final_stop")]
    rig.run()
    assert rig.interrupts == []
    assert rig.sim.track_speeds_m_per_s() == STOPPED
    assert rig.wheel_lines_since(rig.interrupted_at or 0)[0] == STOP_LINE  # restarted with a fresh STOP


def test_ctrl_c_exactly_on_the_stop_write_still_gets_a_stop_through() -> None:
    rig = Rig()
    rig.interrupts = [("a", "drive")]
    swallowed = False

    def lose_the_first_stop(line: bytes) -> None:
        nonlocal swallowed
        if rig.recorder.phase == "final_stop" and line == STOP_LINE and not swallowed:
            swallowed = True
            raise KeyboardInterrupt

    rig.before_request = lose_the_first_stop
    rig.run()
    assert swallowed and rig.sim.track_speeds_m_per_s() == STOPPED


def test_a_stop_lost_to_wifi_after_ctrl_c_is_resent() -> None:
    rig = Rig()
    rig.interrupts = [("a", "drive")]
    lost = 0

    def lose_two_stops(line: bytes) -> None:
        nonlocal lost
        if rig.recorder.phase == "final_stop" and line == STOP_LINE and lost < 2:
            lost += 1
            raise TimeoutError("timed out")

    rig.before_request = lose_two_stops
    rig.run()
    assert lost == 2 and rig.sim.track_speeds_m_per_s() == STOPPED


def test_a_dead_link_is_reported_as_stop_not_confirmed(capsys: pytest.CaptureFixture[str]) -> None:
    rig = Rig()
    rig.interrupts = [("a", "drive")]

    def wifi_down_after_interrupt(line: bytes) -> None:
        if rig.recorder.phase == "final_stop":
            raise TimeoutError("timed out")

    rig.before_request = wifi_down_after_interrupt
    assert not rig.run()
    assert "STOP NOT CONFIRMED" in capsys.readouterr().err
    assert rig.sim.track_speeds_m_per_s() != STOPPED  # honest: the board never heard it


# --- Speed cap and the guard -----------------------------------------------------


def wheel_commands_on_the_wire(rig: Rig) -> list[dict[str, float]]:
    commands = [json.loads(line) for _, line in rig.requests]
    return [command for command in commands if command["T"] == 1]


def test_nothing_above_the_cap_is_ever_encoded(monkeypatch: pytest.MonkeyPatch) -> None:
    encoded: list[Command] = []

    def spy(command: Command, *, speed_cap_m_per_s: float = DEFAULT_SPEED_CAP_M_PER_S) -> bytes:
        encoded.append(command)
        return encode_command(command, speed_cap_m_per_s=speed_cap_m_per_s)

    monkeypatch.setattr(client_module, "encode_command", spy)
    rig = Rig()
    assert rig.run()
    wheels = [command for command in encoded if isinstance(command, WheelSpeedCommand)]
    assert any(not command.is_stop for command in wheels)
    assert all(abs(c.left_m_per_s) <= 0.10 and abs(c.right_m_per_s) <= 0.10 for c in wheels)
    on_wire = wheel_commands_on_the_wire(rig)
    assert all(abs(c["L"]) <= 0.10 and abs(c["R"]) <= 0.10 for c in on_wire)
    assert {c["L"] for c in on_wire} == {0.0, drive.DRIVE_SPEED_M_PER_S}


def test_configured_limits_are_the_agreed_ones() -> None:
    assert drive.CLIENT_CONFIG.speed_cap_m_per_s == 0.10
    assert drive.CLIENT_CONFIG.lease_s == 0.5
    assert drive.DRIVE_SPEED_M_PER_S == 0.05


@pytest.mark.parametrize("speed_m_per_s", [0.11, 0.5, float("nan")])
def test_a_drive_speed_over_the_cap_is_refused_and_never_reaches_the_wire(
    monkeypatch: pytest.MonkeyPatch, speed_m_per_s: float
) -> None:
    monkeypatch.setattr(drive, "DRIVE_SPEED_M_PER_S", speed_m_per_s)
    rig = Rig()
    assert not rig.run()
    assert rig.check.results == []
    assert all((command["L"], command["R"]) == STOPPED for command in wheel_commands_on_the_wire(rig))


# --- Polling and the CSV ---------------------------------------------------------


def rows(rig: Rig) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(rig.csv.getvalue())))


def test_polls_run_at_about_10_hz_from_start_to_finish() -> None:
    rig = Rig()
    rig.run()
    polls = [t_s for t_s, line in rig.requests if line == POLL_LINE]
    gaps = [later - earlier for earlier, later in itertools.pairwise(polls)]
    assert 0.09 <= sum(gaps) / len(gaps) <= 0.12
    assert max(gaps) <= 0.15


def test_csv_logs_commands_and_measurements_in_time_order() -> None:
    rig = Rig()
    rig.run()
    logged = rows(rig)
    assert tuple(logged[0]) == drive.CSV_FIELDS
    times = [float(row["t_monotonic_s"]) for row in logged]
    assert times == sorted(times)
    assert {row["phase"] for row in logged} >= {"idle", "drive", "observe", "lease_running", "silent", "final_stop"}
    moving = [row for row in logged if row["event"] == "feedback" and row["phase"] == "drive" and row["step"] == "a"]
    assert moving and moving[-1]["commanded_left_m_per_s"] == "0.05" and moving[-1]["measured_left_m_per_s"] == "0.05"


def test_csv_shows_the_board_still_holding_the_last_command_during_the_silence() -> None:
    rig = Rig()
    rig.run()
    silent = [row for row in rows(rig) if row["phase"] == "silent" and row["event"] == "feedback"]
    assert {row["commanded_left_m_per_s"] for row in silent} == {"0.05"}
    assert {row["measured_left_m_per_s"] for row in silent} == {"0.05", "0.0"}


def test_csv_records_failed_writes() -> None:
    rig = Rig(("go a",))

    def fail_one_poll(line: bytes) -> None:
        rig.before_request = None
        raise TimeoutError("timed out")

    rig.before_request = fail_one_poll
    rig.run()
    assert "write_failed" in {row["event"] for row in rows(rig)}


def test_default_recording_path_is_gitignored() -> None:
    path = drive.new_csv_path(drive.RECORDINGS_DIR, datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    assert path == REPO / "recordings" / "ugv01_drive_check_20260102T030405Z.csv"
    assert subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=REPO, check=False).returncode == 0


def test_refuses_to_start_without_a_terminal() -> None:
    """Without one, Ctrl+C would not reach the tool. Exits before any request is made."""
    env = os.environ | {"PYTHONPATH": str(REPO / "src")}
    finished = subprocess.run(
        [sys.executable, str(TOOL_PATH), "--http", "192.0.2.7"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )
    assert finished.returncode == 2 and "needs a terminal" in finished.stderr


# --- What counts as stopped ------------------------------------------------------


def test_stop_time_runs_to_the_start_of_the_final_still_run() -> None:
    samples = [sample(10.1, 0.05), sample(10.2, 0.03), sample(10.3, 0.0), sample(10.4, 0.0), sample(10.5, 0.0)]
    assert drive.time_to_still_s(samples, 10.0) == pytest.approx(0.3)


def test_a_lone_zero_while_creeping_is_not_a_stop() -> None:
    samples = [sample(10.1, 0.03), sample(10.2, 0.0), sample(10.3, 0.03), sample(10.4, 0.0), sample(10.5, 0.0)]
    assert drive.time_to_still_s(samples, 10.0) is None
    samples += [sample(10.6, 0.0)]
    assert drive.time_to_still_s(samples, 10.0) == pytest.approx(0.4)


def test_a_reading_on_the_threshold_counts_as_moving() -> None:
    assert not drive.Sample(0.0, 0.005, 0.0).still
    assert not drive.Sample(0.0, 0.0, -0.005).still
    assert drive.Sample(0.0, 0.0049, -0.0049).still


def test_no_readings_after_the_stop_event_is_not_a_stop() -> None:
    assert drive.time_to_still_s([], 10.0) is None
