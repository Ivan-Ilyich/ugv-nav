# UGV Nav

A personal engineering and applied ML project: build a ground robot that
autonomously navigates a small defined test area (first a room, then a
balcony), then measure whether a focused ML contribution improves its
perception or navigation.

The project is also a learning exercise. Decisions should be understandable,
experiments reproducible, and claims tied to recorded evidence.

## Current status — 2 October 2026

Repository foundation only; no robot application, dataset, trained model, or
autonomous navigation implementation yet.

- **Jetson:** boots from NVMe; CUDA smoke test passed (4 September). On
  1 October the software baseline was re-checked unchanged (before that day's
  camera-software installs, which are recorded in docs/hardware.md), and the
  Jetson runs untethered on Wi-Fi with key-based SSH, including after a reboot.
- **D435i:** USB 3 on the Jetson; RGB, depth and IMU stream through a source
  build of librealsense 2.58.1 (RSUSB backend), with a stationary record/replay
  check, 1 October; firmware updated to 5.17.3.10, 2 October.
- **Next:** IMU calibration, then talk to the UGV01 controller over serial.
- **Still unverified:** depth quality in balcony light, stock-controller communication,
  physical stop/timeout behavior, sustained onboard compute, and mobile power.

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
| Jetson enclosure | Candidate onboard packaging; mounting and thermals unverified |
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

The only runnable piece so far is `tools/realsense_check.py`, a stationary
camera check run on the Jetson (setup and results in
[docs/hardware.md](docs/hardware.md#streaming-setup-follows-enumeration)). Add a
small module and its dependencies when the next implementation task needs them.
Keep recordings, datasets, model weights, credentials, network configuration,
and private source material outside version control. Track sanitized
instructions, manifests, and results instead.

See [AGENTS.md](AGENTS.md) for working conventions. Hardware configuration and
movement belong to explicit commissioning tasks.
