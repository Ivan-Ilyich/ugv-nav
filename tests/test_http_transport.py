"""HttpTransport against a fake GET function: URLs, reply queueing, failures (no network)."""

from __future__ import annotations

import http.client
import json
import time
import urllib.parse

import pytest

from ugv_nav.ugv01.protocol import MAX_LINE_BYTES, STOP, FeedbackRequest, encode_command
from ugv_nav.ugv01.transport import HttpTransport

POLL_LINE = encode_command(FeedbackRequest.BASE)
BASE_REPLY = b'{"T":1001,"L":0,"R":0,"r":-1.06,"p":0.39,"y":"null","v":11.82}'


class FakeBoard:
    """Records requested URLs and answers like the firmware's ``/js`` handler."""

    def __init__(self, replies: dict[int, bytes] | None = None, error: Exception | None = None) -> None:
        self.replies = replies if replies is not None else {130: BASE_REPLY}
        self.error = error
        self.urls: list[str] = []
        self.timeouts: list[float] = []

    def get(self, url: str, timeout_s: float) -> bytes:
        self.urls.append(url)
        self.timeouts.append(timeout_s)
        if self.error is not None:
            raise self.error
        command = json.loads(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["json"][0])
        return self.replies.get(command["T"], b"null")


def test_command_is_sent_as_urlencoded_json_and_the_reply_is_queued() -> None:
    board = FakeBoard()
    transport = HttpTransport("192.0.2.7", timeout_s=0.25, get=board.get)
    transport.write_line(POLL_LINE)
    assert board.urls == ["http://192.0.2.7/js?json=%7B%22T%22%3A130%7D"]
    assert board.timeouts == [0.25]
    assert transport.read_line(0.0) == BASE_REPLY
    assert transport.read_line(0.0) is None
    assert transport.requests == 1 and transport.failed_requests == 0
    assert transport.last_round_trip_s is not None


@pytest.mark.parametrize("body", [b"", b"null", b"{}", b"  \r\n"])
def test_empty_replies_queue_nothing(body: bytes) -> None:
    transport = HttpTransport("ugv.local", get=FakeBoard({1: body}).get)
    transport.write_line(encode_command(STOP))
    assert transport.read_line(0.0) is None


@pytest.mark.parametrize(
    "error", [TimeoutError("timed out"), ConnectionRefusedError("refused"), http.client.BadStatusLine("x")]
)
def test_request_failures_raise_oserror_and_are_counted(error: Exception) -> None:
    transport = HttpTransport("192.0.2.7", get=FakeBoard(error=error).get)
    with pytest.raises(OSError):
        transport.write_line(POLL_LINE)
    assert transport.requests == 1 and transport.failed_requests == 1
    assert transport.read_line(0.0) is None


@pytest.mark.parametrize("line", [b'{"T":130}', b'{"T":130}\n{"T":1}\n', b"\n"])
def test_bad_framing_is_rejected_before_any_request(line: bytes) -> None:
    board = FakeBoard()
    with pytest.raises(ValueError):
        HttpTransport("192.0.2.7", get=board.get).write_line(line)
    assert board.urls == []


def test_oversized_reply_is_dropped_and_counted() -> None:
    transport = HttpTransport("192.0.2.7", get=FakeBoard({130: b"x" * (MAX_LINE_BYTES + 1)}).get)
    transport.write_line(POLL_LINE)
    assert transport.read_line(0.0) is None
    assert transport.overflowed_replies == 1


def test_closed_transport_refuses_io() -> None:
    board = FakeBoard()
    with HttpTransport("192.0.2.7", get=board.get) as transport:
        transport.write_line(POLL_LINE)
    with pytest.raises(OSError):
        transport.write_line(POLL_LINE)
    with pytest.raises(OSError):
        transport.read_line(0.0)
    assert len(board.urls) == 1


def test_read_line_waits_at_most_its_timeout_when_nothing_is_queued() -> None:
    transport = HttpTransport("192.0.2.7", get=FakeBoard().get)
    start_s = time.monotonic()
    assert transport.read_line(0.02) is None
    assert 0.015 <= time.monotonic() - start_s < 0.5


@pytest.mark.parametrize("host", ["", "http://192.0.2.7", "192.0.2.7/js", "a b", "user@host"])
def test_host_must_be_bare(host: str) -> None:
    with pytest.raises(ValueError):
        HttpTransport(host)


@pytest.mark.parametrize("timeout_s", [0.0, -1.0, 2.5])
def test_timeout_must_be_bounded(timeout_s: float) -> None:
    with pytest.raises(ValueError):
        HttpTransport("192.0.2.7", timeout_s=timeout_s)
