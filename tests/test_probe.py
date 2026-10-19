"""Control-boundary tests for tools/ugv01_probe.py, run against the simulator only."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.parse
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
from ugv_nav.ugv01.transport import HttpTransport

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


def test_probe_over_http_sends_only_stop_and_feedback_requests() -> None:
    replies = {
        130: b'{"T":1001,"L":0,"R":0,"r":-1.06,"p":0.39,"y":"null","v":11.82}',
        126: b'{"T":1002,"r":0,"p":0,"y":0}',
    }
    sent: list[dict[str, object]] = []

    def fake_get(url: str, timeout_s: float) -> bytes:
        command = json.loads(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["json"][0])
        assert isinstance(command, dict) and isinstance(command["T"], int)
        sent.append(command)
        return replies.get(command["T"], b"null")

    log = probe.ProbeLog(start_s=time.monotonic())
    transport = HttpTransport("192.0.2.7", get=fake_get)
    probe.run_probe(transport, listen_s=0.0, samples=3, interval_s=0.05, log=log, expect_boot_text=False)
    assert sent[0] == sent[-1] == {"T": 1, "L": 0.0, "R": 0.0}
    assert {command["T"] for command in sent} <= {1, 126, 130, 139}
    assert all(command.get("L", 0.0) == 0.0 and command.get("R", 0.0) == 0.0 for command in sent)
    assert log.base_valid == 3
