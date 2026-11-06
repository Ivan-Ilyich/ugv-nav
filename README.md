# UGV Nav

A project to build a ground robot that navigates a small test area by itself,
first a room and then a balcony. A classical baseline comes first, then one ML
component, measured to see whether it helps. It is a personal engineering and
applied ML project: decisions should be easy to follow and claims backed by
recorded evidence.

## Status (6 November 2026)

The robot is assembled and its controller answers over Wi-Fi. The first guarded
drive passed with the tracks lifted; it has not driven on the floor yet.

- **First guarded drive:** at 0.05 m/s the tracks stopped 0.26 s after a host
  stop, 0.26 s after a command-lease stop, and 3.26 s after the last command when
  only the controller's 3 s timeout could stop them. One trial each. 0.78 % of
  Wi-Fi requests failed; one aborted a step safely.
- **Camera:** the D435i streams RGB, depth and IMU on the Jetson (librealsense
  2.58.1 from source, firmware 5.17.3.10). A 20-minute soak held 30 fps with no
  lost frames at ~50 °C and ~5 W.
- **Software:** a typed UGV01 adapter with a speed cap, 0.5 s command lease, stop
  priority, re-arm, serial and HTTP transports, and a simulator. 188 tests;
  `mypy --strict` and `ruff` clean. HTTP has driven the real controller with the
  tracks lifted; all other motion control is tested in simulation only.
- **Not yet:** no floor drive or turn; Jetson power from the bank unchecked; no
  teleop, recording, perception or navigation code.
- **Next:** the same stops on the floor, then at the 0.10 m/s cap; then the
  Wi-Fi failures and a Wi-Fi loss test.
- **Target for November:** classical obstacle avoidance on a short route in a
  room, with repeated trials and recorded results. The ML comparison follows.

## Equipment

| Equipment | Role |
| --- | --- |
| Waveshare UGV01, stock controller and drivetrain | Mobile platform |
| NVIDIA Jetson Orin Nano Super Developer Kit, 8 GB | Onboard sensing, navigation, inference |
| RealSense D435i, supplied USB cable, mini tripod | RGB, depth and IMU capture |
| Kingston NV3 1 TB NVMe | Jetson system and recordings |
| UGREEN PB205, X553 charger, PD-to-barrel cable | Planned mobile power; not yet tested |
| Three Molicel P28A cells | UGV01 power; inspected 6 November, no damage |
| Jetson enclosure | On a printed mount (`hardware/jetson-bank-mount/`); thermals unverified |
| MacBook Pro M4, 48 GB | Development, annotation, local ML experiments |
| ThinkPad P50, Ubuntu | Hardware integration and Jetson support |

## Intended demonstration

The UGV follows a repeatable route to a goal in a measured, supervised area,
avoids obstacles and no-go regions, and stops on command or on loss of valid
control or sensor input. The area, surfaces, speed limits, localization method
and pass marks are set before autonomy is tested.
The classical baseline is compared with the same system plus one ML contribution,
on route success, interventions, unsafe attempts, time and compute cost. Failures
are reported, and "ML adds no benefit" is a valid result.

**Candidate ML task:** visual traversability estimation. No model, architecture
or dataset is chosen yet; see the [assessment](docs/plan.md#ml-task-decision).

## Working locally

Python 3.12 and [uv](https://docs.astral.sh/uv/) with the pinned `uv.lock`. On
the Mac: `uv run pytest -q`, `uv run mypy`, `uv run ruff check .`.

- `src/ugv_nav/ugv01/`: UGV01 adapter and simulator
  ([protocol notes](docs/ugv01-protocol.md)).
- `tools/ugv01_probe.py`: read-only first-contact check. Run over Wi-Fi
  (`--http`); the serial route (`--port`) is unverified.
- `tools/ugv01_drive_check.py`: three timed stops with typed confirmations
  ([results](docs/hardware.md#first-guarded-drive-6-november-2026)).
- `tools/realsense_check.py`, `tools/jetson_soak.py`: camera check and soak
  ([results](docs/hardware.md#streaming-setup-follows-enumeration)).

Planned layout (plain Python, no ROS): `ugv01/`, `sensors/`, `recording/`,
`perception/`, `nav/`, `cli/`. Raw data, weights and credentials stay out of git.

More: [log](docs/log.md), [hardware](docs/hardware.md), [plan](docs/plan.md),
[reuse](docs/reuse.md), [conventions](AGENTS.md), [decisions](CLAUDE.md). Developed
with an AI coding assistant; design decisions, tests and hardware work are the owner's.
