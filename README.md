# UGV Nav

A personal engineering and applied ML project: build a ground robot that
autonomously navigates a small defined test area (first a room, then a
balcony), then measure whether a focused ML contribution improves its
perception or navigation.

The project is also a learning exercise. Decisions should be understandable,
experiments reproducible, and claims tied to recorded evidence.

## Status (23 October 2026)

The robot hardware is assembled and the controller answers over Wi-Fi; the
robot has not driven yet.

- **Hardware:** a two-part mount, printed in PETG, is assembled on the UGV01's
  rails to carry the power bank and the Jetson in its case
  (`hardware/jetson-bank-mount/`; the case screws stay loose until the hole
  depth is measured). The Jetson runs untethered on Wi-Fi with key-based SSH.
- **Robot controller, first contact passed (19 October):** read-only, over the
  controller's Wi-Fi/HTTP endpoint, because the mount covers the Jetson's
  40-pin header. Battery 11.5–11.8 V; the onboard IMU sees gravity on z, and
  the controller's roll/pitch agree with its raw accelerometer within 0.24°
  with the robot level. The probe run from the Jetson got 14 of 14 replies,
  median round trip ≈ 18 ms. Only stop and status requests were sent.
- **Camera:** the D435i streams RGB, depth and IMU on the Jetson with
  librealsense 2.58.1 built from source (RSUSB backend), firmware 5.17.3.10. A
  20-minute soak held 30 fps with no lost frames at ~50 °C and ~5 W.
- **Software:** a typed UGV01 controller adapter (`src/ugv_nav/ugv01/`) with a
  speed cap, 0.5 s command lease, stop priority and explicit re-arm, serial
  and HTTP transports, and a simulator; 134 tests, `mypy --strict` and `ruff`
  clean at the repository root. Motion control is tested in simulation only.
- **Not yet:** no drive yet; the Jetson's power path from the power bank and the
  battery cells are not checked; no recording, perception or navigation code.
- **Next:** the first guarded drive, tracks lifted, then on the floor, measuring
  stop time and distance for a host stop, command-lease expiry, the
  controller's 3 s timeout and Wi-Fi loss.
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
| Three Molicel P28A cells | UGV01 power; the controller reports 11.5–11.8 V; cell condition not inspected |
| Jetson enclosure | Assembled, Jetson boots in it; sits on the printed PETG mount on the UGV01 (`hardware/jetson-bank-mount/`), thermals unverified |
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
`uv run ruff check .`.

- `src/ugv_nav/ugv01/`: UGV01 controller adapter (bounded wheel-speed commands,
  command lease and stop handling, feedback parsing, serial and HTTP
  transports) with a simulator; [protocol notes](docs/ugv01-protocol.md).
  The HTTP transport has carried read-only requests to the real controller;
  motion control is tested only in simulation so far.
- `tools/ugv01_probe.py`: read-only first-contact check; it sends only stop
  and feedback requests and prints redacted replies. Run over Wi-Fi
  (`--http`) on 19 October; the serial route (`--port`) is unverified.
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
