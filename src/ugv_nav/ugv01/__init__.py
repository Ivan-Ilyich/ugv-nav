"""Host adapter for the Waveshare UGV01 stock controller (ugv_base_general JSON protocol).

Modules, by role:

- ``protocol``: pure encoding/parsing of the JSON-line protocol (no I/O).
- ``guard``: pure motion guard (finite command lease, stop priority, re-arm).
- ``transport``: device I/O (``Transport`` protocol and a pyserial ``SerialTransport``).
- ``sim``: in-memory ``SimulatedUGV01`` transport; never touches hardware.
- ``client``: ``UGV01Client`` that sends the guard's output over any transport.

Nothing here opens a port at import time. See docs/ugv01-protocol.md.
"""
