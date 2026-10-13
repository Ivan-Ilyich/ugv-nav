"""Data-integrity tests for the pure UGV01 protocol module."""

from __future__ import annotations

import math
import random

import pytest

from ugv_nav.ugv01.protocol import (
    STOP,
    BaseFeedback,
    CommandRejected,
    FeedbackRequest,
    ImuFeedback,
    LineSplitter,
    SpeedRateReport,
    WheelSpeedCommand,
    check_frame,
    encode_command,
    parse_feedback_line,
    redact_for_log,
)

T1001 = b'{"T":1001,"L":0.031,"R":-0.03,"r":1.2,"p":-0.4,"y":87.5,"temp":41.5,"v":11.84}\r\n'


def parse(line: bytes | str) -> list[BaseFeedback | ImuFeedback | SpeedRateReport]:
    return parse_feedback_line(line, received_monotonic_s=12.5, source="hardware")


# --- Encoding ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (STOP, b'{"T":1,"L":0.0,"R":0.0}\n'),  # the spec's normal stop, byte for byte
        (WheelSpeedCommand(0.1, 0.1), b'{"T":1,"L":0.1,"R":0.1}\n'),
        (WheelSpeedCommand(-0.05, 0.1), b'{"T":1,"L":-0.05,"R":0.1}\n'),
        (WheelSpeedCommand(0, -0.0), b'{"T":1,"L":0.0,"R":0.0}\n'),  # ints and -0.0 normalised
        (FeedbackRequest.BASE, b'{"T":130}\n'),
        (FeedbackRequest.IMU, b'{"T":126}\n'),
        (FeedbackRequest.SPEED_RATE, b'{"T":139}\n'),
    ],
)
def test_encoding_is_one_exact_json_line(command: WheelSpeedCommand | FeedbackRequest, expected: bytes) -> None:
    assert encode_command(command) == expected


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (math.nan, 0.0),
        (0.0, math.inf),
        (-math.inf, 0.0),
        (0.1001, 0.0),  # just above the default 0.10 m/s cap
        (0.0, -0.11),
        (2.5, 2.5),  # the firmware would ignore it *and* refresh its heartbeat
        (True, 0.0),
        ("0.1", 0.0),
        (None, 0.0),
        (10**400, 0.0),
    ],
)
def test_encoder_rejects_non_finite_non_numeric_and_over_cap(left: object, right: object) -> None:
    with pytest.raises(CommandRejected):
        encode_command(WheelSpeedCommand(left, right))  # type: ignore[arg-type]


def test_speed_cap_is_inclusive_and_configurable() -> None:
    assert encode_command(WheelSpeedCommand(0.1, -0.1)) == b'{"T":1,"L":0.1,"R":-0.1}\n'
    assert encode_command(WheelSpeedCommand(0.3, 0.0), speed_cap_m_per_s=0.3) == b'{"T":1,"L":0.3,"R":0.0}\n'


@pytest.mark.parametrize("cap", [0.0, -0.1, 0.51, 2.0, math.nan, math.inf])
def test_speed_cap_cannot_be_configured_beyond_the_absolute_ceiling(cap: float) -> None:
    with pytest.raises(ValueError):
        encode_command(STOP, speed_cap_m_per_s=cap)


@pytest.mark.parametrize("line", [b'{"T":130}', b'{"T":130}\n{"T":1}\n', b"\n", b'{"T":1,\n"L":0}\n'])
def test_frame_check_rejects_anything_but_one_terminated_line(line: bytes) -> None:
    with pytest.raises(ValueError):
        check_frame(line)


# --- Feedback parsing ----------------------------------------------------------


def test_base_feedback_fields_units_and_receipt_time() -> None:
    assert parse(T1001) == [
        BaseFeedback(
            left_m_per_s=0.031,
            right_m_per_s=-0.03,
            roll_deg=1.2,
            pitch_deg=-0.4,
            yaw_deg=87.5,
            battery_v=11.84,
            esp32_temp_c=41.5,
            received_monotonic_s=12.5,
            source="hardware",
            valid=True,
        )
    ]


def test_feedback_with_string_yaw_and_no_temp_is_valid() -> None:
    [feedback] = parse(b'{"T":1001,"L":0,"R":0,"r":0.5,"p":0.1,"y":"null","v":12.1}')
    assert isinstance(feedback, BaseFeedback)
    assert feedback.valid and feedback.stationary
    assert feedback.yaw_deg is None and feedback.esp32_temp_c is None


@pytest.mark.parametrize(
    "line",
    [
        b'{"T":1001,"L":"0.1","R":0}',
        b'{"T":1001,"L":0.1}',
        b'{"T":1001,"L":null,"R":0}',
        b'{"T":1001,"L":NaN,"R":0}',
        b'{"T":1001,"L":0,"R":-Infinity}',
        b'{"T":1001,"L":1e999,"R":0}',
        b'{"T":1001,"L":true,"R":0}',
        b'{"T":1001,"L":255,"R":255}',  # PWM counts, as open-loop main types can report
    ],
)
def test_bad_speed_fields_are_flagged_invalid(line: bytes) -> None:
    [feedback] = parse(line)
    assert isinstance(feedback, BaseFeedback)
    assert not feedback.valid and feedback.problem
    assert not feedback.stationary


@pytest.mark.parametrize(
    "line",
    [
        b'{"T":1001,"L":0.1,"R"',  # cut mid-line
        b"Initialize LittleFS for Flash files ctrl.",
        b"[missionPlay finished.]",
        b'[StepNum: 1 ] - {"T":138,"L":1,"R":1}',  # boot-mission dump
        b'{"T":1,"L":0.1,"R":0.1}',  # echo of host commands
        b'{"T":130}',
        b'{"T":139}',
        b'{"T":"1001","L":0,"R":0}',
        b'{"T":1001.5,"L":0,"R":0}',
        b"\xff\xfe\x00garbage\x80",
        b"[[[[" * 300,
        b'{"a":' * 1500 + b"0" + b"}" * 1500,  # deeper than Python's recursion limit
        b"",
    ],
)
def test_noise_partial_lines_and_echoes_yield_no_feedback(line: bytes) -> None:
    assert parse(line) == []


def test_truncated_feedback_never_yields_a_message() -> None:
    complete = T1001.rstrip()
    for cut in range(len(complete)):
        assert parse(complete[:cut]) == []


def test_glued_wifi_status_is_split_from_the_following_feedback() -> None:
    line = b'{"ip":"192.0.2.1","rssi":-48}{"T":1001,"L":0.05,"R":0.04,"r":0,"p":0,"y":0,"v":11.9}\r\n'
    [feedback] = parse(line)
    assert isinstance(feedback, BaseFeedback)
    assert feedback.valid and (feedback.left_m_per_s, feedback.right_m_per_s) == (0.05, 0.04)


def test_imu_and_speed_rate_replies() -> None:
    imu_line = b'{"T":1002,"r":0.1,"p":0.2,"y":3,"ax":10,"ay":-5,"az":998,"gx":0.5,"gy":0,"gz":-0.25,"mx":12,"my":-3}'
    [imu] = parse(imu_line)
    assert isinstance(imu, ImuFeedback)
    assert imu.valid and imu.accel_mg == (10.0, -5.0, 998.0) and imu.gyro_deg_per_s == (0.5, 0.0, -0.25)
    assert imu.mag_ut is None  # mz missing
    [rate] = parse(b'{"T":139,"L":1,"R":0.5}')
    assert isinstance(rate, SpeedRateReport) and rate.valid
    [bad_rate] = parse(b'{"T":139,"L":1.5,"R":0.5}')
    assert isinstance(bad_rate, SpeedRateReport) and not bad_rate.valid


def test_random_bytes_never_raise() -> None:
    rng = random.Random(20261002)
    alphabet = b'{}[]":,.-+0123456789eETLRnull truefalse NaN\\\r\x00\xff'
    for _ in range(3000):
        line = bytes(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        for message in parse(line):
            assert isinstance(message.valid, bool)


# --- Line reassembly and log redaction -----------------------------------------


def test_line_splitter_reassembles_byte_by_byte_and_strips_crlf() -> None:
    splitter = LineSplitter()
    data = b'noise\r\n\r\n{"T":1001,"L":0,"R":0}\r\n{"T":13'
    lines: list[bytes] = []
    for index in range(len(data)):
        lines += splitter.feed(data[index : index + 1])
    assert lines == [b"noise", b'{"T":1001,"L":0,"R":0}']
    assert splitter.feed(b'0}\n') == [b'{"T":130}']


def test_line_splitter_drops_overlong_lines_and_recovers() -> None:
    splitter = LineSplitter(max_line_bytes=16)
    assert splitter.feed(b"x" * 40) == []
    assert splitter.feed(b"y" * 40 + b"\nok\r\n") == [b"ok"]
    assert splitter.feed(b"z" * 20 + b"\nfine\n") == [b"fine"]
    assert splitter.overflowed_lines == 2


def test_redaction_masks_credentials_and_addresses() -> None:
    raw = (
        '{"ip":"192.0.2.10","rssi":-50,"sta_ssid":"home-net","sta_password":"hunter2",'
        '"ap_password":"se\\"cret"} MAC: AA:BB:CC:DD:EE:FF'
    )
    redacted = redact_for_log(raw)
    for secret in ("192.0.2.10", "home-net", "hunter2", "cret", "AA:BB:CC:DD:EE:FF"):
        assert secret not in redacted
    assert '"rssi":-50' in redacted
    assert "hunt" not in redact_for_log('{"sta_password":"hunt')  # value cut mid-line
