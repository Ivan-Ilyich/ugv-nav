# AMP code reuse assessment

Inspected **29 September 2026**, read-only.

- Source: AMP, `100_Software/app/fleet_manager/`.
- Checkout revision: `14198a5c264d608fac53a06b72b663da4c4d45ce`
  (7 September 2026); working tree clean at inspection.
- Files reviewed: `AGENTS.md`, `README.md`, `main.py`, `requirements.txt`, and
  `scripts/sample_ws_client.py`.
- **Imported code: none.** The next Ethernet/camera checkpoint has no use for a
  telemetry web service. Keep this provenance record for a later concrete need.

## Useful parts and boundaries

| Part | Potential reuse | Limitation |
| --- | --- | --- |
| Pydantic `TelemetryPacket` | Pattern for a typed, documented telemetry contract | Fake pose/status fields are not a sensor/control schema; add frames, acquisition timestamps, source mode and validity when needed. |
| `build_fake_telemetry` and mission helpers | Synthetic input for a future local viewer or parser test | A scripted scenario, not a physics simulator, dataset or controller. Some fields use wall-clock time; deterministic mission sequencing does not mean byte-identical packets. |
| `/health` and `/ws/telemetry` | Small local presentation-service example | Each client starts its own fake mission; health reports the service, not hardware readiness. |
| Bounded sample WebSocket client | Manual smoke check for a future telemetry endpoint | It prints 55 packets; it is not a recording/replay or failure-recovery implementation. |

The generated `emergency_stop` state freezes a fake pose. It provides no physical
stop, watchdog, obstacle sensing or link-loss guarantee. If reused, retain an
explicit simulation name and machine-readable source mode, and keep it separate
from the physical command path.

## Dependency compatibility

The existing pins are `fastapi==0.110.0`, `uvicorn[standard]==0.28.0`, and
`websockets==12.0`. There is no declared Python version or full transitive lock.
Do not copy these pins into a new runtime by default.

Current FastAPI has moved to Pydantic v2, and websockets changed its default
asyncio implementation/aliases in version 14. Review the
[FastAPI migration guide](https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/)
and [websockets upgrade guide](https://websockets.readthedocs.io/en/stable/howto/upgrade.html)
when selecting versions. The existing Pydantic v1/v2 serialization fallback is
historical compatibility code, not a reason to support both in a new module.

If a backend becomes necessary, choose the target Python versions first, resolve
a current compatible stack on macOS and aarch64 Linux, check Uvicorn/WebSocket
behavior and optional dependencies, then pin the tested environment. No new
dependency or compatibility claim for Jetson is made by this bootstrap.

## Verification performed during assessment

Both Python files parsed. In the existing source environment, with bytecode
writes disabled, 100 generated packets passed JSON serialization, bounded
progress, frozen stop-pose and completed-mission checks. The direct async health
function returned `telemetry: simulated`.

Environment: Python 3.9.6, FastAPI 0.110.0, Uvicorn 0.28.0, websockets 12.0,
Pydantic 2.13.4, Starlette 0.36.3. These are observed source-environment versions,
not recommended pins. No packages were installed; no HTTP/WebSocket server or
hardware was exercised. No tracked automated test suite was found.

## Attribution for any future import

No tracked LICENSE/NOTICE/COPYING file was found in the source repository, and
the two Python files contain no third-party attribution notice. This does not
establish a license for redistribution. Before importing, establish the code's
applicable rights, record exact source paths/revision and modifications, and
preserve any upstream copyright/license notices. Review dependency licenses as
well. Nothing has been relicensed or vendored here.
