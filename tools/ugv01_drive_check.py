#!/usr/bin/env python3
"""FIRST GUARDED DRIVE of the UGV01 over Wi-Fi: three timed stops. THIS MOVES THE MOTORS.

After a typed confirmation, each step drives both tracks forward at 0.05 m/s for
1.0 s through ``UGV01Client`` (cap 0.10 m/s, 0.5 s lease), then ends the motion a
different way. The printed time starts at the "stop event":

  step  how the motion ends                            stop event
  a     the tool calls ``client.stop()``               first STOP written
  b     the tool stops submitting but keeps ticking;   first STOP written (by the
        the client stops the tracks at lease expiry    client, at lease expiry)
  c     the tool stops ticking: no STOP is sent, so    last T:1 written (the expiry
        only the firmware heartbeat can stop them      cannot be seen from here)

"Stopped" means the start of the final run of at least ``STILL_SAMPLES`` polls with
|L| and |R| below 0.005 m/s, worked out after the window ends. A single low reading
proves nothing: feedback moves in steps (about 0.025 m/s with no T:1 going out), so it
can read zero while the tracks creep. Times are good to about one poll (0.1 s).

T:130 is polled at about 10 Hz from start to finish. Every T:1 written and T:1001
read goes to a CSV in the gitignored ``recordings/``, flushed as it happens.
``commanded`` is the last T:1 that reached the board, so it stays non-zero during
step c's silence.

Step c cannot use ``tick()``, which would write STOP when the lease ends, so
``RecordingTransport.poll`` sends T:130 directly. That cannot move the robot and
does not refresh the heartbeat. Step c is bounded: ``HEARTBEAT_WATCH_S`` after the
last T:1 the tool sends STOP whatever happened, and reports a heartbeat failure if
the tracks had not stopped.

Ctrl+C (also SIGTERM or an SSH hang-up) writes STOP and keeps resending it for
``FINAL_STOP_S``. It only reaches this process from a terminal, so the tool refuses
to start without one: use ``ssh jetson`` or ``ssh -t``. While Wi-Fi is down no STOP
can arrive, and only the heartbeat or the power switch can stop the tracks.

    cd ~/ugv-nav
    PYTHONPATH=src .venv/bin/python tools/ugv01_drive_check.py --http <board address>

``--steps c`` runs only the named steps, each with its typed confirmation.

Exit status: 0 if every selected step ran clean and the final stop was confirmed by
fresh feedback, 2 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import json
import select
import signal
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Final, TextIO

from ugv_nav.ugv01.client import ClientConfig, ClientStatus, UGV01Client
from ugv_nav.ugv01.guard import DEFAULT_LEASE_S, StopReason, SubmitResult
from ugv_nav.ugv01.protocol import (
    DEFAULT_SPEED_CAP_M_PER_S,
    FIRMWARE_HEARTBEAT_TIMEOUT_S,
    STOP,
    BaseFeedback,
    CommandType,
    FeedbackRequest,
    SourceMode,
    WheelSpeedCommand,
    encode_command,
    parse_feedback_line,
)
from ugv_nav.ugv01.transport import HttpTransport, Transport

CLIENT_CONFIG: Final = ClientConfig(speed_cap_m_per_s=DEFAULT_SPEED_CAP_M_PER_S, lease_s=DEFAULT_LEASE_S)
DRIVE_SPEED_M_PER_S: Final = 0.05
DRIVE_S: Final = 1.0

STILL_BELOW_M_PER_S: Final = 0.005
STILL_SAMPLES: Final = 3
"""Consecutive polls below the threshold that count as stopped; see the module docstring."""

TICK_S: Final = 0.01
"""Loop period. Well under the client's 0.1 s send period: a loop at exactly that
period would skip a send whenever jitter woke it just early, halving the poll rate."""

OBSERVE_S: Final = 2.0
"""How long steps a and b keep watching after the stop event (the client resends STOP for 1 s)."""

LEASE_MARGIN_S: Final = 0.1
"""Step b waits this long past the lease before asking the guard why it stopped."""

HEARTBEAT_WATCH_S: Final = 5.0
"""Silent window of step c, from the last T:1: the 3 s heartbeat, then time to decelerate and settle."""

READY_TIMEOUT_S: Final = 2.0
"""Longest wait for fresh feedback showing still tracks before a step may arm."""

FINAL_STOP_S: Final = 1.5
"""How long the exit path keeps ticking, so a STOP lost to a Wi-Fi hiccup is resent."""

POLL_LINE: Final = encode_command(FeedbackRequest.BASE)
RECORDINGS_DIR: Final = Path(__file__).resolve().parents[1] / "recordings"
CSV_FIELDS: Final = (
    "t_monotonic_s",
    "step",
    "phase",
    "event",
    "commanded_left_m_per_s",
    "commanded_right_m_per_s",
    "measured_left_m_per_s",
    "measured_right_m_per_s",
)


class DriveAborted(Exception):
    """A step could not go on. The run ends and the exit path stops the robot."""


@dataclass(frozen=True, slots=True)
class Sample:
    """One valid T:1001: track speeds in m/s and the host monotonic time it was read."""

    t_s: float
    left_m_per_s: float
    right_m_per_s: float

    @property
    def still(self) -> bool:
        """True when both tracks read below the stopped threshold."""
        return abs(self.left_m_per_s) < STILL_BELOW_M_PER_S and abs(self.right_m_per_s) < STILL_BELOW_M_PER_S


def time_to_still_s(samples: Sequence[Sample], stop_event_s: float) -> float | None:
    """Seconds from ``stop_event_s`` to the start of the still run that ends ``samples``.

    ``samples`` are the readings from the stop event to the end of the window.
    Returns None if that final run is shorter than ``STILL_SAMPLES``, which
    includes tracks still moving when the window ended.
    """
    still_run = 0
    for sample in reversed(samples):
        if not sample.still:
            break
        still_run += 1
    if still_run < STILL_SAMPLES:
        return None
    return samples[-still_run].t_s - stop_event_s


class RecordingTransport:
    """Passes the client's traffic to the real transport and logs what crossed the link.

    The only line it originates is T:130 (``poll``), so the motors stay behind
    the client's guard. Logging here rather than in the step code means the CSV
    shows what was on the wire, whoever wrote it.
    """

    def __init__(self, inner: Transport, csv_file: TextIO, clock: Callable[[], float]) -> None:
        self._inner = inner
        self._file = csv_file
        self._writer = csv.writer(csv_file)
        self._clock = clock
        self._commanded = STOP
        self.step = "-"
        self.phase = "idle"
        self.wheel_writes: list[tuple[float, WheelSpeedCommand]] = []
        """Every T:1 that reached the transport: (monotonic time just before the write, command)."""
        self.samples: list[Sample] = []
        """Every valid T:1001 read, in order."""
        self._writer.writerow(CSV_FIELDS)

    @property
    def source_mode(self) -> SourceMode:
        """The wrapped transport's mode."""
        return self._inner.source_mode

    def write_line(self, line: bytes) -> None:
        """Send first and log after, so a logging error can never hold back a STOP."""
        sent_s = self._clock()
        try:
            self._inner.write_line(line)
        except OSError:
            self._log(sent_s, "write_failed")
            raise
        message = json.loads(line)
        if message["T"] == CommandType.SPEED_CTRL:
            self._commanded = WheelSpeedCommand(message["L"], message["R"])
            self.wheel_writes.append((sent_s, self._commanded))
            self._log(sent_s, "command")

    def read_line(self, timeout_s: float) -> bytes | None:
        """Return the next board line, logging any T:1001 in it."""
        line = self._inner.read_line(timeout_s)
        if line is not None:
            received_s = self._clock()
            for message in parse_feedback_line(line, received_monotonic_s=received_s, source=self.source_mode):
                if isinstance(message, BaseFeedback):
                    self._record_feedback(message)
        return line

    def close(self) -> None:
        """Close the wrapped transport."""
        self._inner.close()

    def poll(self) -> None:
        """Request and read one T:1001 without the client. A failed request is logged, not raised."""
        try:
            self.write_line(POLL_LINE)
            while self.read_line(0.0) is not None:
                pass
        except OSError:
            pass  # step c must keep watching through a Wi-Fi hiccup; the CSV has the failure

    def first_stop_write_since(self, t_s: float) -> float | None:
        """Time of the first STOP written at or after ``t_s``, or None."""
        return next((sent_s for sent_s, command in self.wheel_writes if sent_s >= t_s and command.is_stop), None)

    def first_motion_write_since(self, t_s: float) -> float | None:
        """Time of the first non-zero T:1 written at or after ``t_s``, or None."""
        return next((sent_s for sent_s, command in self.wheel_writes if sent_s >= t_s and not command.is_stop), None)

    def last_motion_write_s(self) -> float | None:
        """Time of the last non-zero T:1 written, or None."""
        return max((sent_s for sent_s, command in self.wheel_writes if not command.is_stop), default=None)

    def _record_feedback(self, message: BaseFeedback) -> None:
        t_s = message.received_monotonic_s
        if message.left_m_per_s is None or message.right_m_per_s is None or not message.valid:
            self._log(t_s, "invalid_feedback")
            return
        self.samples.append(Sample(t_s, message.left_m_per_s, message.right_m_per_s))
        self._log(t_s, "feedback", message.left_m_per_s, message.right_m_per_s)

    def _log(
        self, t_s: float, event: str, left_m_per_s: float | None = None, right_m_per_s: float | None = None
    ) -> None:
        self._writer.writerow(
            [
                f"{t_s:.6f}",
                self.step,
                self.phase,
                event,
                self._commanded.left_m_per_s,
                self._commanded.right_m_per_s,
                left_m_per_s,
                right_m_per_s,
            ]
        )
        self._file.flush()


@dataclass(frozen=True, slots=True)
class StepResult:
    """What one step measured. ``problem`` is None only if the step did what it set out to show."""

    step: str
    stop_event: str
    time_to_still_s: float | None
    peak_left_m_per_s: float
    peak_right_m_per_s: float
    problem: str | None
    note: str


class DriveCheck:
    """The three steps. Motion goes only through ``client``; ``recorder`` only logs and polls."""

    def __init__(
        self,
        client: UGV01Client,
        recorder: RecordingTransport,
        *,
        read_typed: Callable[[float], str | None],
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """``read_typed(timeout_s)`` returns a typed line ("" at end of input) or None if none came."""
        self._client = client
        self._recorder = recorder
        self._read_typed = read_typed
        self._sleep = sleep
        self._clock = clock
        self.results: list[StepResult] = []

    def confirmed(self, step: Step) -> bool:
        """Describe ``step`` and keep polling until a line is typed. True only for the exact phrase."""
        self._recorder.step, self._recorder.phase = step.letter, "idle"
        phrase = f"go {step.letter}"
        print(f"\nStep {step.letter}: {step.description}")
        print(f"Type '{phrase}' to run it; anything else ends the run: ", end="", flush=True)
        while True:
            self._client.tick()
            typed = self._read_typed(TICK_S)
            if typed is not None:
                return typed.strip() == phrase

    def get_ready(self) -> None:
        """Tick until fresh feedback shows still tracks; refuse to go on otherwise."""
        deadline_s = self._clock() + READY_TIMEOUT_S
        while self._clock() < deadline_s:
            status = self._client.tick()
            if status.link_up and self._last_reading_still():
                return
            self._sleep(TICK_S)
        raise DriveAborted("no fresh feedback showing the tracks still, so not driving")

    def host_stop(self) -> StepResult:
        """Step a: stop from the host, as soon as the drive ends."""
        start_s = self._clock()
        last_accepted_s = self._drive()
        self._recorder.phase = "observe"
        self._client.stop()
        self._tick_for(OBSERVE_S)
        stop_event_s = self._recorder.first_stop_write_since(last_accepted_s)
        return self._result("a", "first STOP written", stop_event_s, start_s, self._clock())

    def lease_stop(self) -> StepResult:
        """Step b: stop submitting but keep ticking, so the lease and the client end the motion."""
        start_s = self._clock()
        last_accepted_s = self._drive()
        self._recorder.phase = "lease_running"
        cause = self._tick_for(DEFAULT_LEASE_S + LEASE_MARGIN_S).stop_reason
        self._recorder.phase = "observe"
        self._tick_for(OBSERVE_S)
        stop_event_s = self._recorder.first_stop_write_since(last_accepted_s)
        problem = None if cause is StopReason.LEASE_EXPIRED else f"the guard reports {cause}, not lease expiry"
        note = "" if stop_event_s is None else f"{stop_event_s - last_accepted_s:.2f} s after the last accepted command"
        return self._result("b", "client's STOP at lease expiry", stop_event_s, start_s, self._clock(), problem, note)

    def heartbeat_stop(self) -> StepResult:
        """Step c: go silent. Only T:130 is written until the window ends, then the host sends STOP."""
        start_s = self._clock()
        self._drive()
        last_t1_s = self._recorder.last_motion_write_s()
        if last_t1_s is None:
            raise DriveAborted("no motion command reached the board")
        end_s = last_t1_s + HEARTBEAT_WATCH_S
        self._recorder.phase = "silent"
        next_poll_s = self._clock()
        while (now_s := self._clock()) < end_s:
            if now_s >= next_poll_s:
                next_poll_s = now_s + CLIENT_CONFIG.send_period_s
                self._recorder.poll()
            self._sleep(TICK_S)
        self._recorder.phase = "host_stop_after_watch"
        self._client.stop()  # the measurement is over; if the heartbeat failed, this is what stops the tracks
        result = self._result("c", "last T:1 written", last_t1_s, start_s, end_s)
        self._tick_for(CLIENT_CONFIG.stop_resend_s)
        return result

    def stop_and_confirm(self) -> bool:
        """Every exit path ends here: write STOP, tick so it is resent, report whether it took.

        Another Ctrl+C restarts this rather than cutting it short. True if fresh
        feedback reads the tracks still at the end.
        """
        while True:
            try:
                self._recorder.phase = "final_stop"
                self._client.stop()
                status = self._tick_for(FINAL_STOP_S)
                break
            except KeyboardInterrupt:
                continue
        return status.link_up and self._last_reading_still()

    def _drive(self) -> float:
        """Hold both tracks at the drive speed; return when the last command was accepted.

        ``DRIVE_S`` counts from the first T:1 written, which can trail arming by
        up to one send period. Ends by itself: the guard disarms if writes fail.
        """
        self._recorder.phase = "drive"
        if not self._client.arm():
            raise DriveAborted("the client refused to arm")
        last_accepted_s = armed_s = self._clock()
        while True:
            now_s = self._clock()
            first_t1_s = self._recorder.first_motion_write_since(armed_s)
            if first_t1_s is not None and now_s >= first_t1_s + DRIVE_S:
                return last_accepted_s
            result = self._client.send_wheel_speeds(DRIVE_SPEED_M_PER_S, DRIVE_SPEED_M_PER_S)
            if result is not SubmitResult.ACCEPTED:
                raise DriveAborted(f"drive command {result.value}: {self._client.status().stop_detail}")
            last_accepted_s = now_s
            status = self._client.tick()
            if not status.armed:
                raise DriveAborted(f"disarmed during the drive: {status.stop_reason}, {status.io_error}")
            self._sleep(TICK_S)

    def _tick_for(self, duration_s: float) -> ClientStatus:
        """Tick the client for ``duration_s``: read feedback, poll, write what the guard says."""
        end_s = self._clock() + duration_s
        status = self._client.tick()
        while self._clock() < end_s:
            self._sleep(TICK_S)
            status = self._client.tick()
        return status

    def _last_reading_still(self) -> bool:
        return bool(self._recorder.samples) and self._recorder.samples[-1].still

    def _result(
        self,
        step: str,
        stop_event: str,
        stop_event_s: float | None,
        start_s: float,
        end_s: float,
        problem: str | None = None,
        note: str = "",
    ) -> StepResult:
        samples = [sample for sample in self._recorder.samples if start_s <= sample.t_s < end_s]
        still_s = None
        if stop_event_s is not None:
            still_s = time_to_still_s([sample for sample in samples if sample.t_s >= stop_event_s], stop_event_s)
        if problem is None:
            if stop_event_s is None:
                problem = "no STOP reached the board"
            elif all(sample.still for sample in samples):
                problem = "the tracks never read as moving, so this stop time means nothing"
            elif still_s is None:
                problem = "the tracks did not read still by the end of the window"
        return StepResult(
            step=step,
            stop_event=stop_event,
            time_to_still_s=still_s,
            peak_left_m_per_s=max((sample.left_m_per_s for sample in samples), key=abs, default=0.0),
            peak_right_m_per_s=max((sample.right_m_per_s for sample in samples), key=abs, default=0.0),
            problem=problem,
            note=note,
        )


def travel_cm(duration_s: float) -> str:
    """Distance covered at the drive speed, for the step descriptions."""
    return f"{DRIVE_SPEED_M_PER_S * duration_s * 100:.0f} cm"


@dataclass(frozen=True, slots=True)
class Step:
    """One step: its letter (the confirmation phrase is ``go <letter>``), what it does, how to run it."""

    letter: str
    description: str
    run: Callable[[DriveCheck], StepResult]


STEPS: Final = (
    Step(
        "a",
        f"both tracks forward at {DRIVE_SPEED_M_PER_S} m/s for {DRIVE_S} s, then host stop. "
        f"Expected travel about {travel_cm(DRIVE_S)}.",
        DriveCheck.host_stop,
    ),
    Step(
        "b",
        f"same drive, then the host stops sending and the {DEFAULT_LEASE_S} s lease and client stop it. "
        f"Expected travel about {travel_cm(DRIVE_S + DEFAULT_LEASE_S)}.",
        DriveCheck.lease_stop,
    ),
    Step(
        "c",
        f"same drive, then NO stop is sent: only the firmware's {FIRMWARE_HEARTBEAT_TIMEOUT_S:.0f} s heartbeat, "
        f"unverified on this robot, can stop it. Expected travel about "
        f"{travel_cm(DRIVE_S + FIRMWARE_HEARTBEAT_TIMEOUT_S)}. If it fails, the host sends STOP after "
        f"{HEARTBEAT_WATCH_S:.0f} s of silence: about {travel_cm(DRIVE_S + HEARTBEAT_WATCH_S)}.",
        DriveCheck.heartbeat_stop,
    ),
)

PREFLIGHT: Final = """\
UGV01 first guarded drive. THIS MOVES THE MOTORS. Before the first step:
  - tracks off the ground, robot on a stand on the floor (never a desk), until a lifted run has passed;
  - no browser tab open on the board's web page: it resends its last T:1 every 1.5 s;
  - hand on the power switch: the firmware has no latched emergency stop.
Ctrl+C at any point sends stop."""


def describe(result: StepResult) -> str:
    """One step's result for the terminal."""
    if result.time_to_still_s is None:
        timing = "tracks NOT seen still"
    else:
        timing = f"{result.time_to_still_s:.2f} s to |L|,|R| < {STILL_BELOW_M_PER_S} m/s (about +/- 0.1 s)"
    text = (
        f"Step {result.step}: stop event = {result.stop_event}; {timing}; "
        f"peak L {result.peak_left_m_per_s:+.3f}, R {result.peak_right_m_per_s:+.3f} m/s"
    )
    if result.note:
        text += f"; {result.note}"
    if result.problem is not None:
        text += f"\n  PROBLEM: {result.problem}"
    return text


def run_drive_check(check: DriveCheck, steps: Sequence[Step] = STEPS) -> bool:
    """Run ``steps`` in order until one is declined or has a problem. Every way out stops the robot.

    Returns True only if all of them ran clean and the final stop was confirmed.
    """
    ending = "all selected steps done"
    stopped = False
    try:
        for step in steps:
            if not check.confirmed(step):
                ending = "not confirmed, so nothing more moves"
                break
            check.get_ready()
            result = step.run(check)
            check.results.append(result)
            print(describe(result))
            if result.problem is not None:
                ending = f"step {step.letter} had a problem, so nothing more moves"
                break
    except KeyboardInterrupt:
        ending = "Ctrl+C"
    except DriveAborted as error:
        ending = f"aborted: {error}"
    finally:
        stopped = check.stop_and_confirm()
    print(f"\nRun ended: {ending}.")
    if stopped:
        print("Stop confirmed: fresh feedback reads the tracks still.")
    else:
        print(
            "STOP NOT CONFIRMED (link down, or the tracks still read motion). The firmware heartbeat "
            "should act within about 3 s of the last T:1; if the tracks keep moving, use the power switch.",
            file=sys.stderr,
        )
    return stopped and len(check.results) == len(steps) and all(r.problem is None for r in check.results)


def selected_steps(text: str) -> tuple[Step, ...]:
    """argparse type: the steps named by ``text``, always in a, b, c order."""
    if not text or not set(text) <= {step.letter for step in STEPS}:
        raise argparse.ArgumentTypeError("use one or more of the letters a, b, c")
    return tuple(step for step in STEPS if step.letter in text)


def read_typed(timeout_s: float) -> str | None:
    """Return a line typed on stdin ("" at end of input), or None if none came within ``timeout_s``."""
    ready, _, _ = select.select([sys.stdin], [], [], timeout_s)
    return sys.stdin.readline() if ready else None


def new_csv_path(out_dir: Path, now: datetime) -> Path:
    """A timestamped CSV path in ``out_dir``."""
    return out_dir / f"ugv01_drive_check_{now:%Y%m%dT%H%M%SZ}.csv"


def _raise_interrupt(signum: int, frame: FrameType | None) -> None:
    """Make SIGTERM and SIGHUP take the same stopping path as Ctrl+C."""
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--http", metavar="HOST", required=True, help="board address on Wi-Fi")
    parser.add_argument("--steps", type=selected_steps, default=STEPS, help="steps to run, such as c (default abc)")
    parser.add_argument("--out-dir", type=Path, default=RECORDINGS_DIR, help="where the CSV goes")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("needs a terminal, or Ctrl+C will not reach it: log in with 'ssh jetson' or use 'ssh -t'")

    signal.signal(signal.SIGTERM, _raise_interrupt)
    signal.signal(signal.SIGHUP, _raise_interrupt)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = new_csv_path(args.out_dir, datetime.now(UTC))
    print(PREFLIGHT)
    with path.open("x", newline="") as csv_file:  # "x": never overwrite an earlier run
        recorder = RecordingTransport(HttpTransport(args.http), csv_file, time.monotonic)
        client = UGV01Client(recorder, CLIENT_CONFIG)
        try:
            passed = run_drive_check(DriveCheck(client, recorder, read_typed=read_typed), args.steps)
        finally:
            client.close()
    print(f"CSV: {path}")
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
