# UGV Nav

A personal engineering and applied ML project: build a ground robot that
autonomously navigates a small defined test area (first a room, then a
balcony), then measure whether a focused ML contribution improves its
perception or navigation.

The project is also a learning exercise. Decisions should be understandable,
experiments reproducible, and claims tied to recorded evidence.

## Current status — 13 October 2026

Sensors and control software are in place; the robot has not driven yet.

- **Works:** Jetson runs untethered on Wi-Fi with key-based SSH; the D435i
  streams RGB, depth and IMU on the Jetson (source-built librealsense 2.58.1,
  RSUSB backend, firmware 5.17.3.10); a 20-minute streaming soak held 30 fps
  with no lost frames at ~50 °C and ~5 W; the Jetson sits in its case with the
  Wi-Fi antennas fitted.
- **Software:** a typed UGV01 controller adapter (`src/ugv_nav/ugv01/`) with a
  speed cap, 0.5 s command lease, stop priority and explicit re-arm, plus a
  simulator; 111 tests, `mypy --strict` and `ruff` clean. Tested in simulation
  only.
- **Not yet:** the UGV01 controller has not been connected or driven; the
  Jetson and power bank are not mounted on the robot (printed mount in
  `hardware/jetson-bank-mount/`, parts arriving); no recording, perception or
  navigation code yet; battery cells and the PD power cable not inspected.
- **Next:** mount the Jetson and power bank, first read-only contact with the
  UGV01 controller, then the first guarded drive with measured stop and timeout.
- **Target for November:** classical obstacle avoidance on a short route in a
  room, with repeated trials and recorded results. The ML comparison follows.

A dated history is in [docs/log.md](docs/log.md).

See the [hardware baseline and setup notes](docs/hardware.md),
[implementation sequence](docs/plan.md), and [code reuse assessment](docs/reuse.md).

## Equipment

| Equipment | Intended role |
| --- | --- |
| Waveshare UGV01 with stock controller and drivetrain | Mobile platform and deterministic actuation |
| NVIDIA Jetson Orin Nano Super Developer Kit, 8 GB | Onboard sensing, navigation, and inference |
| RealSense D435i, supplied USB cable, mini tripod | RGB/depth/IMU capture and stationary experiments |
| Kingston NV3 1 TB NVMe | Jetson system and local recordings |
| UGREEN PB205, X553 charger, purchased PD-to-barrel cable | Candidate mobile-power setup; integration untested |
| Three Molicel P28A cells | UGV power components; condition and installation unverified |
| Jetson enclosure | Assembled, Jetson boots in it; printed rover mount ordered (`hardware/jetson-bank-mount/`), thermals unverified |
| MacBook Pro M4, 48 GB unified memory | Primary development, annotation, local ML experiments |
| ThinkPad P50 running Ubuntu | Hardware integration and Jetson support |

## Intended demonstration

The UGV follows a repeatable route to a goal inside a measured, supervised test
area — first indoors in a room, then on a balcony with real sunlight and shade — avoids defined obstacles/no-go regions, and stops on command or loss
of valid control/sensor input. Define the area, allowed surfaces, speed limits,
localization method, and acceptance thresholds before testing autonomy.

First establish a classical navigation baseline. Then compare it with the same
system using one ML contribution, reporting route success, interventions, unsafe
attempts, time, and compute cost. A useful result includes failures and a finding
that ML adds no benefit.

**Candidate ML task:** visual traversability estimation. Start by checking what
the camera can observe and what the UGV can actually traverse. No model,
architecture, or dataset has been selected; see the [assessment](docs/plan.md#ml-task-decision).

## Working locally

Python code uses Python 3.12 and [uv](https://docs.astral.sh/uv/) with the
pinned `uv.lock`. On the Mac: `uv run pytest -q`, `uv run mypy` and
`uv run ruff check src tests tools`.

- `src/ugv_nav/ugv01/`: UGV01 controller adapter (bounded wheel-speed commands,
  command lease and stop handling, feedback parsing) with a simulator;
  [protocol notes](docs/ugv01-protocol.md). Tested only in simulation so far.
- `tools/ugv01_probe.py`: read-only first-contact check for a commissioning
  session; it listens, sends only stop and feedback requests, and prints
  redacted replies. Not yet run on hardware.
- `tools/realsense_check.py` and `tools/jetson_soak.py`: camera stream check and
  20-minute soak, run on the Jetson in its own venv (setup and results in
  [docs/hardware.md](docs/hardware.md#streaming-setup-follows-enumeration)).

Planned layout (plain Python, no ROS): `ugv01/` control, `sensors/` camera,
`recording/` write and replay, `perception/` depth to obstacles, `nav/` pose
and planner, `cli/` teleop/record/replay/drive. Add a module and its
dependencies when the next implementation task needs them. Keep recordings, datasets, model weights, credentials, network
configuration, and private source material outside version control. Track
sanitized instructions, manifests, and results instead.

See [AGENTS.md](AGENTS.md) for working conventions and [CLAUDE.md](CLAUDE.md)
for current decisions and the plan. The project is developed with an AI coding
assistant; design decisions, tests and hardware work are the owner's.
