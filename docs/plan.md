# Implementation sequence

Written **29 September 2026**; updated **7 November 2026**. Step 1 (access and
sensors) was done on 1–2 October. Steps 2–4 (safe control, record and replay,
classical autonomy) are in `CLAUDE.md`, which wins here: the plan to 19 November,
then full go-to-goal after it. This file covers what comes next.

## Delivery steps

| Step | Deliverable | Done when |
| --- | --- | --- |
| 5. Focused ML lifecycle | Label guide, session-split dataset, simple baseline, one candidate | Training and held-out evaluation reproduce from manifests; results are compared with the frozen classical baseline and reported as in "Evaluation design". Decide whether to integrate. |
| 6. Jetson comparison | Deployed model; paired trials | Export parity and latency measured (see "Evaluation design"). Matched routes with ML off and on; benefit and regressions reported. |

Tools: librealsense for capture (and its
[recording format](https://github.com/realsenseai/librealsense/blob/master/doc/record-and-playback.md)),
NumPy and OpenCV for geometry, a training framework for the chosen experiment.

Pose, if dead reckoning is not good enough: AprilTags or visual-inertial odometry
(cuVSLAM, RTAB-Map). Measure drift against known locations. No GNSS or lidar.

Balcony: bounded driving, once the balcony rule in `CLAUDE.md` is met.

## ML task decision

**Visual traversability is a plausible candidate. Commit only after a data and
geometry pilot.**

Traversability means whether this robot, with its footprint, clearance, load and
speed, can use a region under test conditions. Appearance cannot show traction,
hidden holes or clearance, so start with a narrow visible-ground and no-go estimate.

The pilot measures D435i depth on the balcony in sun and shade, at texture changes,
obstacle edges and plants; a nominal range is no guarantee
([D435i](https://www.realsenseai.com/products/depth-camera-d435i/),
[D400 depth guidance](https://www.realsenseai.com/wp-content/uploads/2020/03/BKM-For-Tuning-D435-and-D415-Cameras-Webinar_Rev3.pdf)).
Labels come from our own recordings; outside labels are not ground truth for this
robot. The pilot ends in a short decision note:

1. Can calibrated depth support a geometric baseline at the needed stopping
   distance? Measure valid coverage, errors and frame age.
2. Can a reviewer label traversable, blocked and uncertain regions consistently?
   Check a small second-pass sample for disagreement.
3. What does geometry miss that appearance might catch (a rug edge, mats, plant
   soil, drains)? With no repeatable gap, ML has nothing to win: change the task.
4. Can a small model train locally and meet a latency and memory budget on the M4
   and the Jetson?

If it holds up, compare a depth-only free-space estimate with a compact supervised
model. Candidate: labels from where the robot drove plus depth-confirmed obstacles,
frozen pretrained features (DINOv2-style) with a small head, and hand labels only
for the frozen test set. The model may add cost or no-go areas, or abstain; it must
not override the physical stop path or turn missing geometry into free space. Model
family, input resolution and RGB versus RGB-D stay open.

## Evaluation design

The rules are in `CLAUDE.md`. In addition:

- Where practical, also split by day, route and lighting. Freeze the label policy
  with the test set.
- Record preprocessing, dependency versions, data hashes, checkpoint and training cost.
- Report per-class precision/recall and IoU, the rate of blocked regions called
  traversable, unknown coverage and errors by condition.
- Before deployment, check predictions after export or quantization. Latency covers
  capture to planner; report p50/p95, frame age, memory, power mode and thermals.
- Alternate route order where practical; record weather and surface. Report
  denominators, including path length. Replay supports perception comparisons; only
  physical trials show navigation effects. A higher pixel score alone is not an
  improvement.
