# Implementation sequence

Written **29 September 2026**; status updated **2 October 2026**: step 1 is
largely done (USB-independent SSH over Wi-Fi; stationary RGB, depth and IMU
streaming; camera firmware 5.17.3.10 since 2 October); IMU calibration and depth
quality in balcony light remain open. Test area (2 October): first a room, then a balcony. Each step
ends with a small observable result and recorded limitations. Hardware work
proceeds in explicit commissioning tasks. Historical software/ROS/model plans
are references, not selected architecture.

## Delivery steps

| Step | Small deliverable | Observable completion criterion |
| --- | --- | --- |
| 1. Stationary access and sensors | Network SSH independent of USB; D435i USB 3 enumeration, then a pinned camera stack | Fresh SSH survives removal of USB networking; matching camera device enumerates at `5000M`. In the subsequent streaming check, capture RGB/depth and inspect IMU, record profiles/timing/calibration and a fixed-duration stability result. |
| 2. Deterministic UGV control | Identify stock firmware/transport and implement a small typed command/feedback adapter | In an explicitly commissioned bounded test, zero/stop commands, command expiry, application exit/crash, link loss and reconnect have measured outcomes. Motion stays inside declared speed/duration limits; no stale command resumes movement. |
| 3. Record and replay | One capture tool, versioned manifest, and replay reader | A recorded session replays with matching frame counts/order, timestamps, calibration, depth units and control/feedback events. Dropped/stale data is surfaced; replay cannot send commands to hardware. |
| 4. Classical autonomy | Geometry-based obstacle/no-go representation, a verified pose source, and bounded route following | Complete repeated trials to a defined goal inside the measured test area (room, then balcony). Freeze a baseline configuration and record failures, stops, interventions, route time, and pose error. |
| 5. Focused ML lifecycle | Label guide, session-separated dataset, simple baseline and one trained/fine-tuned candidate | Reproduce training and held-out evaluation from versioned manifests/configuration; report class metrics, dangerous errors, uncertainty and condition-specific failures. Decide whether the candidate merits integration. |
| 6. Jetson comparison | Deploy the selected model and run paired classical/ML-assisted trials | Check exported-model parity; measure end-to-end latency, memory, thermals and stale-frame behavior. Repeat matched routes with ML off/on; report benefit, regressions, and limits. |

Steps 2 and 3 can share a logging contract, but autonomous motion depends on
measured stop/timeout behavior and reliable sensing. A stationary data pilot can
begin before driving. Do not mark a step complete from a simulated status field.

For each result record date, code revision (or uncommitted state), configuration,
input/session identifiers, artifact hashes, commands, measurements and limits.
Raw recordings stay outside Git; sanitized manifests and concise results belong
here. Choose numeric pass/fail limits before the corresponding test and record
actual measurements, including failures.

## Control and navigation decisions

First inspect the stock UGV01 protocol, firmware and available feedback. Do not
assume wheel odometry, a hardware emergency stop, or a controller watchdog works.
Define finite command leases, input bounds, stop priority, a monotonic deadline,
and explicit re-arming after faults. If the stock controller cannot stop after
host/link failure, resolve that blocker before autonomous driving; repeatedly
sending zero from a healthy host is insufficient evidence.

Before a ground test, document the operator's immediate stop method, test bounds,
speed cap, timeout and acceptable stopping time/distance. Verify them under the
actual power, payload and surface conditions. Sensor/pose staleness and unknown
space must resolve conservatively. ML must not override the physical stop path
or turn missing geometry into confirmed free space.

The classical baseline needs localization as well as obstacle avoidance. Choose
the smallest observable pose method after checking feedback and balcony imagery;
camera odometry, wheel feedback or a surveyed visual-marker arrangement are
options to evaluate, not established capabilities. Measure drift against known
locations. No GNSS/lidar capability is assumed.

Use established tools when their interfaces solve a demonstrated need:
librealsense for capture, NumPy/OpenCV for geometry and inspection, and a training
framework for the selected experiment. Evaluate ROS 2/Nav2 when pose, transforms,
sensor and velocity interfaces justify it. Select a compatible distribution for
the verified machines; do not inherit an old ROS distribution or create empty
packages now. Native SDK recording/replay is enough for the first sensor slice;
pin the SDK and verify the capture/replay round trip together. The upstream
[recording guide](https://github.com/realsenseai/librealsense/blob/master/doc/record-and-playback.md)
and [Nav2 setup prerequisites](https://docs.nav2.org/rolling/configuration_and_development/first_time_robot_setup_guide/)
are implementation references, not installed capabilities.

## ML task decision

**Assessment: visual traversability is a plausible candidate; commit only after
a data and geometry pilot.** The available RGB/depth camera and onboard compute
justify investigation. They do not yet establish sensing quality in sunlight,
labels, model throughput, or actual terrain capability.

Traversability means whether this robot, with its footprint, clearance, load and
speed, can use a region under the declared test conditions. Surface appearance
alone cannot establish traction, supporting strength, hidden holes, or clearance.
Start with a narrow visible-ground/no-go estimate for the defined area; retain
an unknown/ignore category rather than forcing ambiguous pixels into free space.

The D435i supplies RGB and stereo depth, with IMU data (streaming through the
RSUSB build since 1 October; not yet calibrated). Depth in balcony sunlight must
be measured on the chosen surfaces, distances and lighting; do not assume every pixel is
valid or use a nominal camera range as a navigation guarantee. The first pilot
should include sun/shade, texture changes, obstacle edges and representative
vegetation, while keeping ground truth manually inspectable. See the official
[D435i information](https://www.realsenseai.com/products/depth-camera-d435i/)
and [D400 depth
guidance](https://www.realsenseai.com/wp-content/uploads/2020/03/BKM-For-Tuning-D435-and-D415-Cameras-Webinar_Rev3.pdf).

No labelled terrain dataset, recording collection, training code, or model
artifact was found in the inspected technical source tree. Existing simulated
telemetry cannot train visual traversability. Start with local sample capture
before selecting an external dataset, pretrained weights, or architecture.
External semantic labels may help initialize an experiment, but are not ground
truth for this robot's ability to travel; check license and domain fit first.
[RELLIS-3D](https://github.com/unmannedlab/RELLIS-3D) is one outdoor semantic-data
candidate to inspect later; its platform, sensors and class definitions differ.

The pilot should produce a short decision note answering:

1. Can calibrated depth support a geometric baseline at the required stopping
   distance? Measure valid coverage, errors and frame age in representative scenes.
2. Can a reviewer consistently label visible traversable, blocked and uncertain
   regions? Define the robot-specific rule and inspect a small second-pass sample
   for disagreement. RGB-D frames alone do not certify physical traversability.
3. What does geometry miss that appearance-based learning might resolve? If there
   is no repeatable useful gap, narrow/change the ML task before model selection.
4. Can a small candidate train locally and meet an onboard latency/memory budget?
   Benchmark a sample on the M4 and Jetson; 48 GB/8 GB memory capacities are not
   throughput guarantees. Do not assume Mac and Jetson training runtimes match.

If the pilot supports it, compare a depth/geometry-only free-space estimate with
a compact supervised ground-region model. Use the learned output as a bounded
planner cost or additional no-go signal with an explicit abstention policy.
Keep the model family, input resolution and RGB versus RGB-D choice open until
sample quality, label cost and measured compute justify them.

## Evaluation design

- Split by recording session and preferably day/route/lighting; adjacent video
  frames must not leak across train/validation/test. Freeze split manifests and
  the label policy. Tune thresholds on validation data only.
- Train/fine-tune one justified candidate and compare it to a simple non-learned
  baseline. Record seeds, preprocessing, dependency versions, data hashes,
  checkpoint identity and training cost.
- Report per-class precision/recall and IoU for region labels, plus the rate of
  blocked regions incorrectly called traversable, unknown coverage and errors
  by condition. Use both inspected examples and aggregate metrics.
- Before deployment, check prediction agreement after export/quantization on a
  fixed sample. Include capture, preprocessing and planner integration in latency
  measurements; report p50/p95, frame age, memory, power mode and sustained thermals.
- Run repeated matched routes with the same controller, geometry/stop rules,
  speed cap and goals, varying only the ML contribution. Alternate order where
  practical and record weather/surface changes. Report denominators for route
  success, interventions, blocked-region entries/attempts, time and path length.
  Replay supports perception comparisons; physical trials establish navigation
  effects. A changed path or higher pixel score alone is not an improvement.

## Immediate next task

USB-independent SSH and D435i enumeration passed on 1 October 2026
([result](hardware.md#checkpoint-usb-independent-ssh-then-d435i-enumeration)), and
RGB, depth and IMU stream through a source-built librealsense 2.58.1 (RSUSB)
with a stationary record/replay check ([results](hardware.md#streaming-setup-follows-enumeration)).
Camera firmware was updated to 5.17.3.10 on 2 October. For step 2, the UGV01
protocol was researched from the firmware source and a bounded adapter with a
simulator was written ([notes](ugv01-protocol.md)). Next: IMU calibration,
then step 2 —
identify the UGV01 transport and measure its stop/timeout behavior.
