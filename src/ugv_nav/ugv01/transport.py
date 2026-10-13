"""Device I/O: the line-transport interface and a pyserial implementation.

``SerialTransport.open`` is a hardware action and belongs in a scoped
commissioning task. Importing this module opens nothing.
"""

from __future__ import annotations

import os
import time
from collections import deque
from types import TracebackType
from typing import Final, Protocol, Self

import serial

from .protocol import (
    MAX_LINE_BYTES,
    SERIAL_BAUD_RATE,
    LineSplitter,
    SourceMode,
    check_frame,
)

DEFAULT_WRITE_TIMEOUT_S: Final = 0.2
"""A write blocked longer than this raises instead of stalling the control loop."""


def _is_printable(byte: int) -> bool:
    """Printable ASCII, tab, CR or LF: what a correctly framed text line contains."""
    return 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D)


class Transport(Protocol):
    """A newline-framed byte link to the board, real or simulated."""

    @property
    def source_mode(self) -> SourceMode:
        """``"hardware"`` or ``"simulation"``; stamped on every parsed message."""
        ...

    def write_line(self, line: bytes) -> None:
        """Send one line ending in ``\\n``. Raises OSError if the link has failed."""
        ...

    def read_line(self, timeout_s: float) -> bytes | None:
        """Return the next complete line without its terminator, or None after ``timeout_s`` (0 polls).

        Raises OSError if the link has failed.
        """
        ...

    def close(self) -> None:
        """Release the link. Further I/O raises OSError."""
        ...


class SerialTransport:
    """pyserial transport for the board's UART0 (115200 8N1). Opening it touches hardware."""

    source_mode: Final = "hardware"

    def __init__(self, port: serial.Serial, *, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        """Wrap an already open pyserial port; prefer ``SerialTransport.open``."""
        self._serial = port
        self._splitter = LineSplitter(max_line_bytes)
        self._pending: deque[bytes] = deque()
        self.bytes_received = 0
        """Raw bytes read from the port, before line splitting."""
        self.non_printable_bytes = 0
        """Raw bytes outside printable ASCII, tab, CR and LF (many suggest a baud mismatch)."""

    @classmethod
    def open(
        cls,
        port: str,
        *,
        baud_rate: int = SERIAL_BAUD_RATE,
        write_timeout_s: float = DEFAULT_WRITE_TIMEOUT_S,
    ) -> SerialTransport:
        """Open ``port`` at ``baud_rate`` 8N1 (exclusively on POSIX), then clear RTS and DTR.

        On the board's USB-C route a CP2102 drives the ESP32 reset (EN) and boot
        (IO0) pins from DTR/RTS. The lines cannot be kept deasserted across the
        open: the OS typically asserts both when the port opens (Linux does), and
        pyserial applies values set beforehand only afterwards, DTR first. So
        pyserial's defaults (both asserted) are kept and the lines are cleared
        after opening, RTS then DTR, as in Waveshare's demo. Opening the USB-C
        port may still reset (reboot) the board; that must be measured in
        commissioning (a ROM boot banner during the probe's passive listen means
        it did). The 40-pin UART route has no DTR/RTS path.
        """
        link = serial.Serial()
        link.port = port
        link.baudrate = baud_rate
        link.bytesize = serial.EIGHTBITS
        link.parity = serial.PARITY_NONE
        link.stopbits = serial.STOPBITS_ONE
        link.timeout = 0
        link.write_timeout = write_timeout_s
        if os.name == "posix":
            link.exclusive = True
        link.open()
        try:
            # RTS first: the intermediate state DTR-on/RTS-off only touches IO0, a
            # strapping pin sampled at reset. Clearing DTR first would pass through
            # DTR-off/RTS-on, which pulls EN low (reset) on the usual auto-reset
            # circuit.
            link.rts = False
            link.dtr = False
        except BaseException:
            link.close()
            raise
        return cls(link)

    @property
    def overflowed_lines(self) -> int:
        """Lines dropped for exceeding the maximum line length."""
        return self._splitter.overflowed_lines

    @property
    def pending_bytes(self) -> int:
        """Received bytes not yet ended by a newline (not counted in any line)."""
        return self._splitter.pending_bytes

    def write_line(self, line: bytes) -> None:
        """Send one line; raises ValueError for bad framing and OSError on failure or short write."""
        check_frame(line)
        written = self._serial.write(line)
        if written != len(line):
            raise OSError(f"short write: {written} of {len(line)} bytes")

    def read_line(self, timeout_s: float) -> bytes | None:
        """Return the next complete line, waiting at most ``timeout_s`` (real monotonic time)."""
        deadline_s = time.monotonic() + max(0.0, timeout_s)
        while not self._pending:
            remaining_s = deadline_s - time.monotonic()
            self._serial.timeout = max(0.0, remaining_s)
            chunk = self._serial.read(max(1, self._serial.in_waiting))
            self.bytes_received += len(chunk)
            self.non_printable_bytes += sum(1 for byte in chunk if not _is_printable(byte))
            self._pending.extend(self._splitter.feed(chunk))
            if not self._pending and remaining_s <= 0:
                return None  # at most one non-blocking read after the deadline
        return self._pending.popleft()

    def close(self) -> None:
        """Close the port."""
        self._serial.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
