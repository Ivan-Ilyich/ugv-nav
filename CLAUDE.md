# UGV Nav — project notes for Claude

Read this first. Last updated **13 October 2026**. Deeper detail lives in
`README.md`, `docs/plan.md`, `docs/hardware.md`, `docs/log.md` (dated history),
`docs/reuse.md` and `AGENTS.md`.

## What we're building

A small ground robot (Waveshare UGV01 + Jetson Orin Nano + RealSense D435i) that
drives itself to a goal inside a defined area while avoiding obstacles and no-go
regions. On top of a working **classical (geometry-only) baseline**, we add **one
ML component** and measure whether it actually helps. The candidate ML task is
**visual traversability**: from the camera, which ground can this robot drive on?
Test area (decided 2 Oct 2026): first my room, then my balcony (real sunlight and
shade for the camera; small, so it must be bounded — see "Protect the hardware").

## Why

A personal engineering and applied-ML learning project and portfolio piece. It
grew out of **AMP** (`~/dev/amp`), an autonomous-mowing startup idea that was
dropped on 1 September 2026. The hardware and some ideas carried over; the
mower, the startup and its governance did not. The goal is hands-on skill and
reproducible results across hardware bring-up, control, sensing, data, classical
robotics, ML and edge deployment. "ML didn't help" is an acceptable result.

## How we work (decided 30 September 2026)

- **Progress over paperwork.** Short notes, concrete next steps, no excessive
  hedging. Do the small step, record the result in a few lines, move on. Don't
  over-engineer: build only what the next result needs.
- **People are not at risk (the balcony edge is the one exception); the hardware is.** Testing happens in my room, then on
  my balcony, with a small, slow robot, so skip heavyweight safety process (the AMP docs' version was
  for a cutting mower and does not apply). Put the care into **not damaging
  components** — see "Protect the hardware" below.
- **Results should be able to support a paper.** Measure honestly and report
  failures and negative results plainly — see "Evaluation standard" below.
- Where `AGENTS.md` or `docs/plan.md` are more cautious or formal than this
  file, **this file wins**.
- **Deadline:** the repo is evidence of Python programming for an MSc
  application (University of Hull, submit by **19 November 2026**). A reviewer
  may read the code and ask the owner to explain it. Keep the code readable,
  tested, and honestly described; refresh the README before submission.
- `~/dev/amp` is a **read-only reference**. Its startup, gate and governance
  documents are history, not requirements.
- **Machine access** (IPs, hostnames, users, SSH key paths) is in
  `CLAUDE.local.md`, which is gitignored. Read it when you need to connect to
  something. Never copy those details into tracked files, commits or PRs.
- Commit when a piece of work is done (small, logical commits; don't push
  unless asked). Keep raw recordings, datasets and weights
  out of git (`/data/`, `/recordings/`, `/local/` etc. are ignored).
- Prefer simple typed Python and established libraries; add structure and
  dependencies only when the next step needs them.
- **End of every task (decided 2 Oct 2026):** update "Next steps" in this file and
  today's note in `vault/Daily/`, then tell me whether it is a good moment to
  `/clear` (it is when the work is recorded here, in `docs/` or the vault, and
  the next step does not depend on details that exist only in the conversation).
- **Learning vault (`vault/`, gitignored, Obsidian; decided 2 Oct 2026).** I am new
  to everything here except software development and want to understand it, not
  only see it done. After each working session update the vault: task notes in
  `vault/Tasks/` (status/owner/scheduled/completed properties drive the
  dashboard), the day's note in `vault/Daily/`, a plain-language page in
  `vault/Results/` for any new result, and new or updated concept notes in
  `vault/Learn/<Area>/` for new jargon (format: `vault/Templates/Concept.md`).
  Explain in plain words, link concepts with `[[Exact Title]]`, never put
  addresses, serials or passwords there.

## Protect the hardware

What actually matters here is not breaking things:

- **Power:** check voltage and polarity before connecting any supply or barrel
  plug to the Jetson (9–20 V DC, centre positive) or the UGV board. Insert the
  18650s in the holder's marked orientation. Don't use damaged/dented cells.
- **Falls:** first motor tests with the **wheels/tracks off the ground**; when
  driving, stay on the floor — never on a desk or table.
- **Balcony:** block every gap the robot could fit through or drive off (railing
  gaps, open edges, steps) before driving there, and only drive there after the
  stop and timeout behaviour is verified indoors. A fall breaks the robot and can
  hurt someone below — this is the one place where people could be at risk.
- **Stalls:** don't hold the motors stalled against a wall at high command for long.
- **Jetson:** shut down cleanly (`sudo shutdown now`) rather than pulling power,
  to protect the NVMe filesystem; keep the fan running and airflow clear.
- **Firmware:** before flashing the UGV01's ESP32 or camera firmware, note the
  current version and how to restore it.
- **Cables/connectors:** don't force USB-C or barrel plugs; avoid hot-swapping
  things into the UGV's power path.

## Evaluation standard (paper-quality)

The ML part should be evaluated well enough that the result would survive a
reviewer, whichever way it comes out:

- **Split data by recording session, not by frame.** Neighbouring video frames
  are near-duplicates; mixing them across train/test makes a model look far
  better than it is.
- **Freeze the test set** before any tuning; tune thresholds on validation only.
- **Keep an "unknown" class** instead of forcing uncertain pixels into
  "traversable".
- **Compare against a simple non-ML baseline** with the same robot, routes and
  settings, varying only the ML component.
- **Record enough to reproduce:** date, git revision, config, data/model
  versions, seeds, commands, measurements.
- **Report failures and negative results plainly.** If something fails or ML
  doesn't help, say so, with numbers and examples. "ML added nothing" is a valid
  finding and goes in the results.

## Hardware and machines

| Item | Key facts | Tested by us? |
| --- | --- | --- |
| **Waveshare UGV01** | ESP32 "General Driver for Robots" board; one JSON object per line over UART at 115200 (40-pin header to the Jetson, or the board's USB-C, which Waveshare says needs disassembly). Encoder motors, onboard IMU, 3×18650 with UPS/protection board. Firmware probably `waveshareteam/ugv_base_general` 0.9x (GPL-3.0), but an older incompatible `UGV01_BASE` firmware exists — check the OLED version line at power-on. From source, unmeasured: 3 s motion timeout refreshed only by motion commands from **any** source (serial, Wi-Fi web UI, ESP-NOW); no latched emergency stop; the board runs a Wi-Fi access point with a published default password (anyone nearby can drive it); the same speed value is m/s in closed loop (UGV01 model setting) but raw motor power in open loop. Details: `docs/ugv01-protocol.md` | No |
| **Batteries** | 3× Molicel P28A flat-top *unprotected* cells — this is the type Waveshare asks for (the UGV's board provides protection). Condition unchecked. | No |
| **Jetson Orin Nano Super 8 GB** | JetPack 7.2.1 / L4T R39.2.1, Ubuntu 24.04 aarch64, CUDA 13.2, boots from Kingston NV3 1 TB NVMe. DisplayPort gave no picture → run headless. Dev kit includes a Wi-Fi card. | Bench (4 Sep); SSH, Wi-Fi, baseline (1 Oct) |
| **RealSense D435i** | USB ID `8086:0b3a`; must enumerate at `5000M` (USB 3). We have **one** suitable USB cable — the camera's own, which was also the Jetson USB-SSH cable. | Stationary, indoor (1 Oct) |
| **Jetson mobile power** | UGREEN PB205 power bank + PD-to-barrel cable (recorded as Adafruit 5451, which requests a fixed 15 V and falls back to 9 V or lower; the 20 V version is 5452 — confirm from the cable's label). Check: the voltage actually negotiated under load (~25 W peak + ~2 W camera), power bank idle shut-off, plug fit (Jetson jack 5.5×2.5 mm). | No |
| **MacBook Pro M4, 48 GB** | Main development, annotation and local ML machine. Repo lives here. | — |
| **ThinkPad P50** | Ubuntu 22.04. Jetson flashing/support host (SDK Manager). Reachable over SSH on the home LAN. | — |

## State (13 October 2026)

- **Works:** Jetson untethered on Wi-Fi, key-based SSH; D435i RGB/depth/IMU
  streaming on the Jetson (librealsense 2.58.1 RSUSB build, firmware 5.17.3.10);
  20-min camera soak OK; Jetson in its case with antennas; UGV01 adapter with
  speed cap, command lease, stop priority and simulator — 111 tests, mypy
  strict, ruff clean.
- **Not yet done:** the UGV01 has never been talked to or driven; the Jetson and
  power bank are not on the robot (printed mount arriving 14 Oct); no recording
  tool, no perception, no navigation; batteries and PD cable not inspected.
- Full dated history: `docs/log.md`.

## Plan to 19 November: classical obstacle avoidance in the room

Goal: the robot drives from a start mark to a goal mark (~3–4 m) in my room,
with one or two boxes in the way, stops or steers around them, repeated
trials recorded with numbers. Pose from wheel encoders + gyro yaw (dead
reckoning; enough for a few metres indoors). ML stays after the deadline.

| Week | Deliverable | Done when |
| --- | --- | --- |
| 13–19 Oct | Repo committed and pushed. Mount assembled, batteries/PD cable inspected, Jetson on the bank. **UGV01 first contact** (`tools/ugv01_probe.py`), then first guarded drive: tracks off the ground, then on the floor. | Stop and 3 s timeout measured (time and distance at the speed cap). Recorded in `docs/hardware.md`. → **make the repo public.** |
| 20–26 Oct | `ugv_nav.sensors` (RealSense wrapper from `tools/realsense_check.py`), `ugv_nav.recording` (writer + reader + manifest), `teleop` CLI that drives from the keyboard and records camera + feedback. | A recorded drive replays with matching frame counts and feedback events; replay cannot send commands. |
| 27 Oct–2 Nov | `ugv_nav.perception`: depth → ground-plane removal → obstacle cells in the robot frame; `ugv_nav.nav.pose` from encoder odometry + gyro yaw. Tested on replayed recordings first. | On replay, obstacles at known distances are detected within a stated error; pose error over a 3 m straight run measured with a tape. |
| 3–9 Nov | `ugv_nav.nav.planner` + `drive` CLI: go-to-goal with stop-and-steer around obstacles. | ≥10 trials, table of success / interventions / time / final position error, failures included. |
| 10–19 Nov | Buffer. README results section, a short GIF, final check that the owner can explain `guard.py`, `protocol.py`, the planner. | Submitted. |

## Architecture (decided 13 October 2026): plain Python, no ROS

One package, `src/ugv_nav/`, small modules with clear boundaries; `tools/` and
CLIs call into it. ROS 2 would cost weeks on two OS versions for nothing a
reviewer can see; it can wrap these modules later if ever needed.

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

Rules that keep it explainable: every message and command has units, frame
and timestamp; the guard is the only path to the motors; perception and
planning are pure functions over data so they run identically on replay and
live; one config file per test (speed cap, obstacle distance, goal).

## Next steps

1. **Today:** push the commits (`git push -u origin main` from the Mac); run
   `uv run pytest -q` first.
2. **14 Oct:** mount arrives → assemble per `hardware/jetson-bank-mount/README.md`
   (screws listed there); inspect the three P28A cells (no dents, matching
   voltage) and the PD-to-barrel cable label (5451 = 15 V vs 5452 = 20 V);
   first Jetson boot from the power bank, note the negotiated voltage/behaviour.
3. **UGV01 first contact:** host link decision (40-pin UART vs board USB-C),
   OLED firmware line at power-on, run `tools/ugv01_probe.py` with tracks off
   the ground; then first guarded drive and the stop/timeout measurement.
4. IMU reference readings when convenient (deferred; see `docs/hardware.md`).
5. Home-network maintenance (see `CLAUDE.local.md`).

## Roadmap after 19 November (detail in `docs/plan.md`)

- Balcony: depth quality in sun/shade; bounded driving there.
- Better pose if dead reckoning drifts too much: AprilTags or visual-inertial
  odometry (cuVSLAM / RTAB-Map).
- ML: visual traversability — self-supervised labels from where the robot
  actually drove + depth-confirmed obstacles; frozen pretrained features
  (DINOv2-style) with a small head; hand-label only the frozen test set. The
  test area needs places where geometry alone fails (a rug edge indoors, mats,
  plant soil, drains on the balcony), otherwise ML has nothing to win.
- Deploy on the Jetson; matched routes with ML off vs on.
