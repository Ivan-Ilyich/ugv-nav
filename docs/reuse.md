# AMP code reuse assessment

Inspected **29 September 2026**, read-only.

- Source: AMP, `100_Software/app/fleet_manager/`, revision
  `14198a5c264d608fac53a06b72b663da4c4d45ce` (7 September 2026), clean tree.
- Files reviewed: `AGENTS.md`, `README.md`, `main.py`, `requirements.txt`,
  `scripts/sample_ws_client.py`.
- **Imported code: none.** This record stays for a later concrete need.

## Useful parts and boundaries

| Part | Potential reuse | Limitation |
| --- | --- | --- |
| Pydantic `TelemetryPacket` | Pattern for a typed telemetry contract | Fake pose/status fields; would need frames, timestamps, source mode and validity. |
| `build_fake_telemetry` and mission helpers | Synthetic input for a viewer or parser test | A script, not a physics simulator, dataset or controller. |
| `/health` and `/ws/telemetry` | Small local service example | Each client starts its own fake mission; health says nothing about hardware. |
| Bounded sample WebSocket client | Manual check of a telemetry endpoint | Prints 55 packets; no recording or failure recovery. |

The generated `emergency_stop` state freezes a fake pose. It gives no physical stop,
watchdog or link-loss guarantee. If reused, keep it clearly named as simulation and
separate from the physical command path.

## Dependency compatibility

Existing pins: `fastapi==0.110.0`, `uvicorn[standard]==0.28.0`, `websockets==12.0`.
No declared Python version or full lock, so do not copy them. Current FastAPI uses
Pydantic v2, and websockets changed its asyncio default in version 14 (see the
[FastAPI](https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/)
and [websockets](https://websockets.readthedocs.io/en/stable/howto/upgrade.html)
guides). The Pydantic v1/v2 fallback is no reason to support both. If a backend is
needed, choose the Python version, resolve a stack on macOS and aarch64 Linux, pin it.

## Verification performed during assessment

Both Python files parsed. 100 generated packets passed JSON serialization, bounded
progress, frozen stop-pose and completed-mission checks. The async health function
returned `telemetry: simulated`. Environment: Python 3.9.6, FastAPI 0.110.0, Uvicorn
0.28.0, websockets 12.0, Pydantic 2.13.4, Starlette 0.36.3 (observed, not recommended).
No server or hardware exercised. No tracked test suite found.

## Attribution for any future import

No LICENSE/NOTICE/COPYING file was found, so no licence for redistribution is
established. Before importing, establish the rights, record paths, revision and
changes, and keep upstream notices. Nothing has been relicensed or vendored here.
