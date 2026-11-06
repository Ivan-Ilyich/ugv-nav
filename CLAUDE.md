# UGV Nav — project notes for Claude

Read this first. Last updated **6 November 2026**. More detail: `README.md`,
`docs/plan.md`, `docs/hardware.md`, `docs/log.md`, `docs/reuse.md`, `AGENTS.md`.

## What we're building

A small ground robot (Waveshare UGV01, Jetson Orin Nano, RealSense D435i) that
drives itself to a goal in a defined area, avoiding obstacles and no-go regions.
On a **classical (geometry-only) baseline** we add **one ML component** and measure
whether it helps. Candidate task: **visual traversability** (which ground can this
robot drive on?). Test area (decided 2 Oct 2026): my room, then my balcony.

## Why

A personal learning project and portfolio piece. It grew out of **AMP**
(`~/dev/amp`), a mowing startup idea dropped on 1 September 2026; the hardware and
some ideas carried over. The goal is hands-on skill and reproducible results.
"ML didn't help" is an acceptable result.

## How we work (decided 30 September 2026)

- **Progress over paperwork.** Do the small step, record it in a few lines, move
  on. Build only what the next result needs.
- **Keep everything simple (decided 6 Nov 2026).** Commits, comments, docs,
  reports and code: plain language, short sentences, no jargon unless it is
  the right word and nothing simpler exists. No over-analysis, no extra
  concepts, no edge cases nobody asked about, unless there is an obvious and
  good reason, and then say the reason in one line. A report to the owner
  should fit on one screen: what was done, what was found, what is next.
  Reviewers at Hull will read this repo; write for them.
- **People are not at risk (the balcony edge is the one exception); the hardware
  is.** Small, slow robot, so no heavyweight safety process. The care goes into
  **not damaging components**.
- **Results should be able to support a paper.** Measure honestly; report failures
  plainly.
- Where `AGENTS.md` or `docs/plan.md` are more cautious, **this file wins**.
- **Deadline:** the repo is evidence of Python programming for an MSc application
  (University of Hull, submit by **19 November 2026**). A reviewer may ask the
  owner to explain the code. Keep it readable, tested and honestly described;
  refresh the README before submission.
- `~/dev/amp` is a **read-only reference**; its documents are history, not rules.
- **Machine access** (IPs, hostnames, users, SSH key paths) is in
  `CLAUDE.local.md`. Never copy it into tracked files, commits or PRs.
- Commit finished work in small logical commits; don't push unless asked. Raw
  recordings, datasets and weights stay out of git (`/data/`, `/recordings/`,
  `/local/` etc. are ignored).
- **End of every task (decided 2 Oct 2026):** update "Next steps" and today's
  `vault/Daily/` note, then say whether it is a good moment to `/clear` (it is
  when nothing needed exists only in the conversation).
- **Learning vault (`vault/`, gitignored; decided 2 Oct 2026).** I am new to
  everything except software and want to understand it. After each session update
  `vault/Tasks/` (status/owner/scheduled/completed drive the dashboard),
  `vault/Daily/`, `vault/Results/` for new results and `vault/Learn/<Area>/` for
  new jargon (format: `vault/Templates/Concept.md`). Plain words, `[[Exact Title]]`
  links, no addresses, serials or passwords.

## Protect the hardware

- **Power:** check voltage and polarity before connecting any supply or barrel
  plug to the Jetson (9–20 V DC, centre positive) or the UGV board. Insert the
  18650s in the marked orientation. No damaged or dented cells.
- **Falls:** first motor tests with the **tracks off the ground**; when driving,
  stay on the floor, never on a desk or table.
- **Balcony:** first block every gap the robot could fit through or drive off, and
  drive there only after stop and timeout behaviour is verified indoors. A fall
  can hurt someone below; this is the one place people could be at risk.
- **Stalls:** don't hold the motors stalled against a wall at high command for long.
- **Jetson:** use `sudo shutdown now` rather than pulling power, to protect the
  NVMe filesystem. Keep the fan running and airflow clear.
- **Firmware:** before flashing the ESP32 or camera, note the version and how to
  restore it.
- **Cables:** don't force USB-C or barrel plugs; avoid hot-swapping things into
  the UGV's power path.

## Evaluation standard (paper-quality)

- **Split data by recording session, not by frame;** neighbouring frames are
  near-duplicates.
- **Freeze the test set** before any tuning; tune thresholds on validation only.
- **Keep an "unknown" class** rather than forcing uncertain pixels into "traversable".
- **Compare against a simple non-ML baseline,** varying only the ML component.
- **Record enough to reproduce:** date, git revision, config, data/model versions,
  seeds, commands, measurements.
- **Report failures and negative results plainly,** with numbers and examples.

## Hardware and machines

| Item | Key facts | Tested by us? |
| --- | --- | --- |
| **Waveshare UGV01** | ESP32 board; JSON lines over UART at 115200 or Wi-Fi/HTTP. Encoder motors, IMU, 3×18650. Firmware probably `ugv_base_general` 0.9x. No latched emergency stop. Facts: `docs/ugv01-protocol.md` | Lifted drive at 0.05 m/s (6 Nov) |
| **Batteries** | 3× Molicel P28A flat-top *unprotected* cells, as Waveshare asks (the board protects them). Inspected 6 Nov, no damage. 12.1 V. | Lifted drive (6 Nov) |
| **Jetson Orin Nano Super 8 GB** | JetPack 7.2.1 / L4T R39.2.1, Ubuntu 24.04 aarch64, CUDA 13.2, Kingston NV3 1 TB NVMe. Headless (DisplayPort gave no picture). | Bench (4 Sep); SSH, Wi-Fi, baseline (1 Oct) |
| **RealSense D435i** | USB ID `8086:0b3a`; must enumerate at `5000M`. **One** suitable USB cable, the camera's own. | Stationary, indoor (1 Oct) |
| **Jetson mobile power** | UGREEN PB205 + PD-to-barrel cable. Checks to do: `docs/hardware.md` | No |
| **MacBook Pro M4, 48 GB** | Main development, annotation, local ML. Repo lives here. | — |
| **ThinkPad P50** | Ubuntu 22.04. Jetson flashing host (SDK Manager). SSH on the home LAN. | — |

## State (6 November 2026)

- **Works:** Jetson on Wi-Fi with key-based SSH; D435i RGB/depth/IMU (librealsense
  2.58.1 RSUSB, firmware 5.17.3.10); 20-min soak OK; Jetson in its case on the
  PETG mount (case screws loose until the hole depth is measured).
- **UGV01:** on the home network over Wi-Fi/HTTP. Probe: 0 of 14 requests failed,
  median ≈ 18 ms, battery 11.5–11.8 V. Pitch now reads about +10° with the robot
  not tilted (cause unknown).
- **First guarded drive passed, tracks lifted, 0.05 m/s (6 Nov):** host stop and
  lease stop 0.26 s, firmware heartbeat 3.26 s after the last `T:1`, both tracks
  forward. One trial each. 0.78 % of HTTP requests fail in irregular bursts; any
  failure during a drive disarms.
- **Software:** UGV01 adapter and `tools/ugv01_drive_check.py` (`--steps` retries
  one step). 188 tests, mypy strict, ruff clean.
- **Not yet done:** no floor drive; no turn, so left/right mapping unknown; Jetson
  not run from the bank; PD cable not inspected; no teleop, recording, perception
  or navigation.

## Plan to 19 November: classical obstacle avoidance in the room

The robot drives from a start mark to a goal mark (~3–4 m) in my room, stops or
steers around one or two boxes, and repeated trials are recorded with numbers.
Pose from wheel encoders + gyro yaw (dead reckoning). ML stays after the deadline.

| Week | Deliverable | Done when |
| --- | --- | --- |
| 13–19 Oct | Repo pushed, mount assembled, batteries/PD cable inspected, Jetson on the bank. First contact, then first guarded drive: tracks lifted, then floor. | Stop and 3 s timeout measured (time and distance at the speed cap) in `docs/hardware.md`. → **make the repo public.** |
| 20–26 Oct | `ugv_nav.sensors`, `ugv_nav.recording` (writer, reader, manifest), `teleop` CLI that drives from the keyboard and records camera + feedback. | A recorded drive replays with matching frame counts and feedback events; replay cannot send commands. |
| 27 Oct–2 Nov | `ugv_nav.perception`: depth → ground-plane removal → obstacle cells; `ugv_nav.nav.pose`. Tested on replays first. | Obstacles at known distances detected within a stated error; pose error over a 3 m straight run measured with a tape. |
| 3–9 Nov | `ugv_nav.nav.planner` + `drive` CLI: go-to-goal with stop-and-steer. | ≥10 trials, table of success / interventions / time / final position error, failures included. |
| 10–19 Nov | Buffer. README results section, a short GIF, check the owner can explain `guard.py`, `protocol.py`, the planner. | Submitted. |

## Architecture (decided 13 October 2026): plain Python, no ROS

One package, `src/ugv_nav/`; `tools/` and CLIs call into it. ROS 2 would cost weeks
on two OS versions for nothing a reviewer can see; it can wrap these modules later.

```
ugv_nav/
  ugv01/        protocol, transport, guard (lease/stop/re-arm), client, sim   [exists]
  sensors/      realsense.py — frames keyed by (number, timestamp), IMU sync   [week 2]
  recording/    writer.py, reader.py, manifest (JSON) — replay never actuates  [week 2]
  perception/   obstacles.py — depth → ground plane → obstacle grid           [week 3]
  nav/          pose.py (odom + gyro), planner.py (go-to-goal, stop/steer),
                loop.py (sense → plan → bounded command at a fixed rate)      [week 3–4]
  cli/          teleop, record, replay, drive                                 [weeks 2–4]
```

Every message and command has units, frame and timestamp. The guard is the only
path to the motors. Perception and planning are pure functions over data, so they
run the same on replay and live. One config file per test.

## Next steps

1. **Drive check on the floor**, at least 1 m clear ahead: repeat at 0.05 m/s and measure
   stop distance with a tape. Then the 0.10 m/s cap (change `DRIVE_SPEED_M_PER_S`).
   Retry an aborted step with `--steps`. Run command: `docs/hardware.md`.
2. **Before teleop:** find out why 0.78 % of HTTP requests fail, and decide how
   the client treats one failed request. Command a turn to confirm left/right
   mapping. Test a real Wi-Fi loss.
3. Find out why the board's pitch reads about +10° on a level robot.
4. Gyro bias: samples at rest swing ±2–4 deg/s, so average a few seconds at start-up
   and subtract. Board `r`/`p` can be wrong after a blocking command (`T:407`).
5. Keep ruff clean at the repo root (`uv run ruff check .`; clean since 23 Oct).
6. Measure the Jetson case's bottom-hole depth, then tighten the case screws.
7. `sensors/` + `recording/` (week 2 of the plan) in parallel.
8. Reserve the board's address in the router.

## Roadmap after 19 November (detail in `docs/plan.md`)

- Balcony: depth quality in sun/shade; bounded driving.
- Better pose if needed: AprilTags or visual-inertial odometry (cuVSLAM / RTAB-Map).
- ML: self-supervised labels from where the robot drove + depth-confirmed
  obstacles; frozen pretrained features (DINOv2-style) with a small head; hand-label
  only the frozen test set. The area needs places where geometry alone fails (a rug
  edge, mats, plant soil, drains), or ML has nothing to win.
- Deploy on the Jetson; matched routes with ML off vs on.
