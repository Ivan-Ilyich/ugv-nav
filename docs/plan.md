# Implementation sequence

Written **29 September 2026**; status last updated **6 November 2026**. The plan to
19 November is in `CLAUDE.md`, which wins here. Test area (2 October): a room, then
a balcony. Each step ends with a small observable result and its limits.

## Delivery steps

| Step | Deliverable | Done when |
| --- | --- | --- |
| 1. Stationary access and sensors | SSH independent of USB; D435i at USB 3; pinned camera stack | Fresh SSH survives removing USB networking; camera at `5000M`; RGB, depth and IMU checked with a fixed-duration stability result. |
| 2. Deterministic UGV control | Typed command/feedback adapter | Stop, command expiry, application crash, link loss and reconnect have measured outcomes. Motion stays inside speed and duration limits; no stale command resumes movement. |
| 3. Record and replay | Capture tool, versioned manifest, replay reader | Sessions replay with matching frames, timestamps, calibration, depth units and control events. Dropped or stale data is shown. Replay cannot send commands. |
| 4. Classical autonomy | Geometry obstacle/no-go map, verified pose, bounded route following | Repeated trials to a defined goal inside the measured area. Baseline frozen; failures, stops, interventions, time and pose error recorded. |
| 5. Focused ML lifecycle | Label guide, session-split dataset, simple baseline, one candidate | Training and held-out evaluation reproduce from manifests; class metrics, dangerous errors, uncertainty and failures reported. Decide whether to integrate. |
| 6. Jetson comparison | Deployed model; paired trials | Export parity, latency, memory, thermals and stale frames measured. Matched routes with ML off/on; benefit and regressions reported. |

Autonomous motion depends on measured stop/timeout behaviour and reliable sensing.
A stationary data pilot can start before driving. Never mark a step done from a
simulated status field. Set numeric pass/fail limits before each test. Record
date, code revision, configuration, session identifiers, artifact hashes, commands,
measurements and limits.

## Control and navigation decisions

Do not assume wheel odometry, a hardware emergency stop or a controller watchdog
works. Use finite command leases, input bounds, stop priority, a monotonic deadline
and explicit re-arming. If the controller cannot stop after host or link failure,
fix that before autonomous driving. Sending zero from a healthy host proves nothing.

Before a ground test, write down the immediate stop method, test bounds, speed cap, timeout
and acceptable stopping time and distance, and verify them under real power,
payload and surface conditions. Stale sensors or pose and unknown space resolve
conservatively. ML must not override the physical stop path or turn missing geometry
into confirmed free space.

The baseline needs localization as well as obstacle avoidance. Camera odometry,
wheel feedback or surveyed visual markers are options, not established capabilities.
Measure drift against known locations. No GNSS or lidar is assumed.

Tools: librealsense for capture (pin the SDK and verify the
[recording](https://github.com/realsenseai/librealsense/blob/master/doc/record-and-playback.md)
round trip), NumPy/OpenCV for geometry, a training framework for the chosen
experiment. ROS 2/Nav2 only if ever justified
([setup prerequisites](https://docs.nav2.org/rolling/configuration_and_development/first_time_robot_setup_guide/));
on 13 October we chose plain Python.

## ML task decision

**Visual traversability is a plausible candidate. Commit only after a data and
geometry pilot.** Sunlight sensing quality, labels, model throughput and real terrain
capability are all still unknown.

Traversability means whether this robot, with its footprint, clearance, load and
speed, can use a region under test conditions. Appearance cannot show traction,
hidden holes or clearance. Start with a narrow visible-ground and no-go estimate,
and keep an unknown class.

Measure D435i depth on the real balcony surfaces and light; a nominal range is no
guarantee ([D435i](https://www.realsenseai.com/products/depth-camera-d435i/),
[D400 depth guidance](https://www.realsenseai.com/wp-content/uploads/2020/03/BKM-For-Tuning-D435-and-D415-Cameras-Webinar_Rev3.pdf)).
The IMU streams through the RSUSB build since 1 October, not yet calibrated. The
pilot should cover sun and shade, texture changes, obstacle edges and vegetation.

No labelled terrain dataset, training code or model exists yet, and simulated
telemetry cannot train this. Capture local samples first. External labels are not
ground truth for this robot.
[RELLIS-3D](https://github.com/unmannedlab/RELLIS-3D) is one dataset to inspect
later; check licence and fit.

The pilot ends in a short decision note:

1. Can calibrated depth support a geometric baseline at the needed stopping
   distance? Measure valid coverage, errors and frame age.
2. Can a reviewer label traversable, blocked and uncertain regions consistently?
   Check a small second-pass sample for disagreement.
3. What does geometry miss that appearance might catch? With no repeatable gap,
   change the ML task.
4. Can a small model train locally and meet a latency and memory budget? Benchmark
   on the M4 and Jetson; 48 GB/8 GB capacities are not throughput guarantees.

If it holds up, compare a depth-only free-space estimate with a compact supervised
model, used as a bounded planner cost or extra no-go signal with an explicit
abstention policy. Model family, input resolution and RGB versus RGB-D stay open.

## Evaluation design

The rules are in `CLAUDE.md`. In addition:

- Split by session, and preferably by day, route and lighting. Freeze the label
  policy too.
- Record preprocessing, dependency versions, data hashes, checkpoint and training cost.
- Report per-class precision/recall and IoU, the rate of blocked regions called
  traversable, unknown coverage and errors by condition.
- Before deployment, check predictions after export or quantization. Latency covers
  capture to planner; report p50/p95, frame age, memory, power mode and thermals.
- Alternate route order where practical; record weather and surface. Report
  denominators, including path length. Replay supports perception comparisons; only physical trials show
  navigation effects. A higher pixel score alone is not an improvement.

## Immediate next task

Step 1 is largely done: SSH and D435i enumeration passed on 1 October 2026
([result](hardware.md#checkpoint-usb-independent-ssh-then-d435i-enumeration)), and
RGB, depth and IMU through librealsense 2.58.1 (RSUSB)
([results](hardware.md#streaming-setup-follows-enumeration)). Firmware 5.17.3.10
since 2 October. Still open: IMU calibration (deferred 9 October) and depth quality
in balcony light.

Step 2: protocol and adapter done ([notes](ugv01-protocol.md)), first stops measured
with the tracks lifted on 6 November. Next: "Next steps" in `CLAUDE.md`.
