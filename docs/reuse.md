# AMP code reuse assessment

Inspected **29 September 2026**, read-only. **Imported code: none.**

- Source: AMP, `100_Software/app/fleet_manager/`, revision
  `14198a5c264d608fac53a06b72b663da4c4d45ce` (7 September 2026), clean tree.
- Files reviewed: `AGENTS.md`, `README.md`, `main.py`, `requirements.txt`,
  `scripts/sample_ws_client.py`.
- What it is: a FastAPI service with a Pydantic `TelemetryPacket`,
  `build_fake_telemetry` and mission helpers, `/health` and `/ws/telemetry`, and a
  sample WebSocket client that prints 55 packets. All telemetry is generated; its
  `emergency_stop` state only freezes a fake pose, with no physical stop, watchdog
  or link-loss guarantee.
- Pins: `fastapi==0.110.0`, `uvicorn[standard]==0.28.0`, `websockets==12.0`; no
  declared Python version or full lock.
- Checks: both Python files parsed. 100 generated packets passed JSON serialization,
  bounded progress, frozen stop-pose and completed-mission checks. The async health
  function returned `telemetry: simulated`. Environment: Python 3.9.6, FastAPI
  0.110.0, Uvicorn 0.28.0, websockets 12.0, Pydantic 2.13.4, Starlette 0.36.3
  (observed, not recommended). No server or hardware exercised. No tracked test
  suite found.
- No LICENSE, NOTICE or COPYING file was found, so no licence for redistribution is
  established.
