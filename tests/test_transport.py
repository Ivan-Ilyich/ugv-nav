"""SerialTransport against a fake port: framing, read deadline, write failures (no hardware)."""

from __future__ import annotations

from typing import cast

import pytest
import serial

from ugv_nav.ugv01.transport import SerialTransport

POLL_LINE = b'{"T":130}\n'


class FakePort:
    """Stands in for an open ``serial.Serial``: queued read chunks, recorded writes."""

    def __init__(self, chunks: list[bytes] | None = None, *, write_result: int | Exception | None = None) -> None:
        self.chunks = list(chunks or [])
        self.write_result = write_result  # None: full write; int: bytes written; Exception: raised
        self.timeout: float | None = None
        self.read_timeouts: list[float | None] = []
        self.written: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, size: int) -> bytes:
        self.read_timeouts.append(self.timeout)
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, data: bytes) -> int:
        self.written.append(data)
        if isinstance(self.write_result, Exception):
            raise self.write_result
        return len(data) if self.write_result is None else self.write_result

    def close(self) -> None:
        pass


def transport_for(port: FakePort) -> SerialTransport:
    return SerialTransport(cast("serial.Serial", port))


def test_poll_with_nothing_received_returns_none_after_one_read() -> None:
    port = FakePort()
    assert transport_for(port).read_line(0.0) is None
    assert len(port.read_timeouts) == 1


def test_lines_from_one_chunk_come_back_one_per_call_without_further_reads() -> None:
    port = FakePort([b'{"T":1001,"L":0}\r\n{"T":1001,"L":1}\r\n'])
    transport = transport_for(port)
    assert transport.read_line(0.0) == b'{"T":1001,"L":0}'
    assert transport.read_line(0.0) == b'{"T":1001,"L":1}'
    assert len(port.read_timeouts) == 1


def test_a_line_split_across_reads_is_reassembled_within_the_deadline() -> None:
    port = FakePort([b'{"T":1001', b"}\r", b"\n"])
    assert transport_for(port).read_line(1.0) == b'{"T":1001}'
    timeouts = [timeout for timeout in port.read_timeouts if timeout is not None]
    assert len(timeouts) == 3 and all(0.0 < timeout <= 1.0 for timeout in timeouts)
    assert timeouts == sorted(timeouts, reverse=True)  # recomputed from one deadline


def test_short_write_raises_oserror() -> None:
    with pytest.raises(OSError, match="short write"):
        transport_for(FakePort(write_result=3)).write_line(POLL_LINE)


def test_write_timeout_is_an_oserror_so_the_client_treats_it_as_link_failure() -> None:
    port = FakePort(write_result=serial.SerialTimeoutException("Write timeout"))
    with pytest.raises(OSError):
        transport_for(port).write_line(POLL_LINE)


@pytest.mark.parametrize("line", [b'{"T":130}', b"a\nb\n"])
def test_bad_framing_is_refused_before_anything_is_written(line: bytes) -> None:
    port = FakePort()
    with pytest.raises(ValueError):
        transport_for(port).write_line(line)
    assert port.written == []


def test_unterminated_garbage_shows_in_the_raw_counters() -> None:
    garbage = bytes([0xF8, 0x80, 0x78, 0xFE, 0x00, 0xE0]) * 50  # as at a wrong baud: no newline
    port = FakePort([garbage] * 4)
    transport = transport_for(port)
    assert transport.read_line(0.0) is None
    assert (transport.bytes_received, transport.non_printable_bytes) == (300, 250)
    assert transport.pending_bytes == 300
    assert [transport.read_line(0.0) for _ in range(3)] == [None, None, None]
    assert (transport.bytes_received, transport.non_printable_bytes) == (1200, 1000)
    assert transport.overflowed_lines == 1 and transport.pending_bytes == 0


def test_open_clears_rts_then_dtr_only_after_the_port_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class RecordingSerial:
        """Records open and control-line changes; touches no device."""

        def __setattr__(self, name: str, value: object) -> None:
            if name in ("dtr", "rts"):
                events.append(f"{name}={value}")
            object.__setattr__(self, name, value)

        def open(self) -> None:
            events.append("open")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(serial, "Serial", RecordingSerial)
    SerialTransport.open("not-a-port")
    assert events == ["open", "rts=False", "dtr=False"]
