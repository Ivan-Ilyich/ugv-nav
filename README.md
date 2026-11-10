# UGV Nav

A personal project to build a small tracked robot that will drive itself to a goal
in a measured, supervised area (first a room, then a balcony), avoid obstacles and
no-go regions, and stop on command or when valid control or sensor input is lost.
A classical (geometry-only) baseline comes first. Then one ML component will be
added and compared with it on route success, interventions, unsafe attempts, time
and compute cost. Failures are reported, and "ML adds no benefit" is a valid result.

**Candidate ML task:** visual traversability (which ground can this robot drive
on?). No model, architecture or dataset is chosen yet; see the
[assessment](docs/plan.md#ml-task-decision).

**Hardware:** Waveshare UGV01 tracked robot (stock controller and drivetrain), NVIDIA
Jetson Orin Nano Super 8 GB, RealSense D435i camera, UGREEN PB205 power bank (planned
Jetson power) and a printed mount modelled in Python
([`hardware/jetson-bank-mount/`](hardware/jetson-bank-mount/)). Development and local
ML on a MacBook Pro M4 (48 GB); the Jetson is flashed from a ThinkPad P50 (Ubuntu).

## Status (10 November 2026)

The Jetson sits on the robot's mount and the robot's controller answers over
Wi-Fi. The first guarded drive passed on the floor.

- **Stops at 0.05 m/s on the floor** ([results](docs/hardware.md#first-guarded-drive-6-november-2026)):
  the tracks stopped 0.26 s after a host stop, 0.26 s after the stop the client
  sends when a command's 0.5 s lease runs out, and 3.26 s after the last command
  when only the controller's 3 s timeout could stop them. One trial each. 0.78 %
  of Wi-Fi requests failed; one aborted a step safely.
- **Camera:** the D435i streams RGB, depth and IMU on the Jetson. A 20-minute soak
  held 30 fps with no lost frames at ~50 °C and ~5 W
  ([results](docs/hardware.md#streaming-setup-follows-enumeration)).
- **Software:** a typed adapter for the robot's controller: speed cap, each command
  expires after 0.5 s, a stop always wins, explicit re-arm; serial and HTTP
  transports; a simulator. 193 tests; `mypy --strict` and `ruff` clean. HTTP has
  driven the real robot on the floor; all other motion control is tested in
  simulation only.
- **Not yet:** no stop-distance measurement or turn; the Jetson is not yet powered from its
  battery bank; no keyboard driving (teleop), recording, perception or navigation
  code.
- **Target for 19 November:** driving from the keyboard (teleop) with camera and
  feedback recorded, and an autonomous stop before an obstacle. Full go-to-goal and
  the ML comparison follow.

## Working locally

Python 3.12 and [uv](https://docs.astral.sh/uv/) with the pinned `uv.lock`:
`uv run pytest -q`, `uv run mypy`, `uv run ruff check .`.

- `src/ugv_nav/ugv01/`: adapter and simulator ([protocol notes](docs/ugv01-protocol.md)).
- `tools/ugv01_probe.py`: read-only check of the controller over Wi-Fi (`--http`);
  the serial route (`--port`) has not been tried on the robot.
- `tools/ugv01_drive_check.py`: the three timed stops, each after a typed
  confirmation.
- `tools/realsense_check.py`, `tools/jetson_soak.py`: camera check and soak.

Plain Python, no ROS; the planned modules are in [CLAUDE.md](CLAUDE.md). Raw data,
weights and credentials stay out of git.

More: [log](docs/log.md), [hardware](docs/hardware.md), [plan](docs/plan.md),
[code reuse](docs/reuse.md), [conventions](AGENTS.md), [decisions](CLAUDE.md).
Developed with an AI coding assistant.
