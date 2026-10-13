"""Control-boundary tests for tools/ugv01_probe.py, run against the simulator only."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

from ugv_nav.ugv01.protocol import (
    STOP,
    FeedbackRequest,
    WheelSpeedCommand,
    encode_command,
)
from ugv_nav.ugv01.sim import ManualClock, SimulatedUGV01

PROBE_PATH = Path(__file__).resolve().parents[1] / "tools" / "ugv01_probe.py"
STOP_LINE = encode_command(STOP)
ALLOWED_LINES = {STOP_LINE} | {encode_command(request) for request in FeedbackRequest}


def load_probe() -> ModuleType:
    """Import the probe script as a module (tools/ is not a package)."""
    spec = importlib.util.spec_from_file_location("ugv01_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


probe = load_probe()


def test_probe_writes_only_stop_and_feedback_requests_and_starts_and_ends_with_stop() -> None:
    sim = SimulatedUGV01(ManualClock())
    log = probe.ProbeLog(start_s=time.monotonic())
    probe.run_probe(sim, listen_s=0.0, samples=3, interval_s=0.0, log=log)
    assert set(sim.host_lines) <= ALLOWED_LINES
    assert sim.host_lines[0] == sim.host_lines[-1] == STOP_LINE
    assert len(sim.host_lines) == 1 + 2 + 3 + 1
    assert all((e.left_m_per_s, e.right_m_per_s) == (0.0, 0.0) for e in sim.motion_log)


@pytest.mark.parametrize("command", [WheelSpeedCommand(0.0, 0.01), WheelSpeedCommand(-0.01, 0.0)])
def test_send_refuses_any_motion_command(command: WheelSpeedCommand) -> None:
    sim = SimulatedUGV01(ManualClock())
    log = probe.ProbeLog(start_s=0.0)
    with pytest.raises(RuntimeError):
        probe.send(sim, command, log)
    assert sim.host_lines == [] and log.sent == set()


def test_send_allows_negative_zero_as_a_stop() -> None:
    sim = SimulatedUGV01(ManualClock())
    probe.send(sim, WheelSpeedCommand(-0.0, 0.0), probe.ProbeLog(start_s=0.0))
    assert sim.host_lines == [STOP_LINE]


def test_feedback_before_the_first_send_is_counted_as_unsolicited() -> None:
    sim = SimulatedUGV01(ManualClock())
    log = probe.ProbeLog(start_s=0.0)
    feedback = b'{"T":1001,"L":0,"R":0,"v":12.0}'
    log.record(feedback, 1.0)
    probe.send(sim, FeedbackRequest.BASE, log)
    log.record(feedback, 2.0)
    summary = log.summary()
    assert summary["base_feedback_valid"] == 2
    assert summary["unsolicited_base_feedback"] == 1
