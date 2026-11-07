# UGV Nav — project notes for Claude

Read this first. More detail: `README.md` (overview and status), `docs/hardware.md`
(measurements), `docs/ugv01-protocol.md` (robot controller), `docs/plan.md` (after
19 November), `docs/log.md` (history), `AGENTS.md` (coding rules).

## What we're building

A small ground robot (Waveshare UGV01, Jetson Orin Nano, RealSense D435i) that
drives itself to a goal in a defined area, avoiding obstacles and no-go regions.
On a **classical (geometry-only) baseline** we add **one ML component** and measure
whether it helps. Candidate task: **visual traversability** (which ground can this
robot drive on?). Test area: my room, then my balcony.

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
- Where `AGENTS.md` or `docs/plan.md` are more cautious, **this file wins**.
- **Deadline:** the repo is evidence of Python programming for an MSc application
  (University of Hull, submit by **19 November 2026**). A reviewer may ask the
  owner to explain the code. Keep it readable, tested and honestly described.
- `~/dev/amp` (AMP, the project this one grew out of) is a **read-only
  reference**; its documents are history, not rules.
- **Privacy:** machine access (IPs, hostnames, users, SSH key paths) is in
  `CLAUDE.local.md`. Keep it out of tracked files, commits and PRs, together with
  credentials, MACs, serials, private messages, purchase documents and the AMP
  vault; commit only sanitized summaries.
- Commit finished work in small logical commits; don't push unless asked. Raw
  recordings, datasets and weights stay out of git.
- **End of every task (decided 2 Oct 2026):** check `git diff --check`, secrets and
  untracked files; update "Next steps" and the vault (below); say whether it is a
  good moment to `/clear` (it is when nothing needed exists only in the
  conversation).
- **Learning vault (`vault/`, gitignored; decided 2 Oct 2026).** I am new to
  everything except software and want to understand it. After each session update
  `vault/Tasks/` (status/owner/scheduled/completed drive the dashboard), today's
  `vault/Daily/` note, `vault/Results/` for new results and `vault/Learn/<Area>/`
  for new jargon (format: `vault/Templates/Concept.md`). Plain words,
  `[[Exact Title]]` links, no addresses, serials or passwords.

## Protect the hardware

The robot is small and slow, so people are not at risk, except at the balcony edge.
No heavyweight safety process; the care goes into **not damaging components**.

- **Power:** check voltage and polarity before connecting any supply or barrel
  plug to the Jetson (9–20 V DC, centre positive) or the UGV board. Insert the
  18650s in the marked orientation. No damaged or dented cells.
- **Falls:** first motor tests with the **tracks off the ground**; when driving,
  stay on the floor, never on a desk or table.
- **Balcony:** first block every gap the robot could fit through or drive off, and
  drive there only after stop and timeout behaviour is verified indoors. A fall
  can hurt someone below.
- **Stalls:** don't hold the motors stalled against a wall at high command for long.
- **Jetson:** use `sudo shutdown now` rather than pulling power, to protect the
  NVMe filesystem. Keep the fan running and airflow clear.
- **Firmware:** before flashing the ESP32 or camera, note the version and how to
  restore it.
- **Cables:** don't force USB-C or barrel plugs; avoid hot-swapping things into
  the UGV's power path. The camera's own USB cable is the only suitable one.

## Evaluation standard (paper-quality)

- **Split data by recording session, not by frame;** neighbouring frames are
  near-duplicates.
- **Freeze the test set** before any tuning; tune thresholds on validation only.
- **Keep an "unknown" class** rather than forcing uncertain pixels into "traversable".
- **Compare against a simple non-ML baseline,** varying only the ML component.
- **Set numeric pass/fail limits before each test** (on the robot: stop method,
  speed cap, acceptable stop time and distance). Never mark a step done from
  simulation.
- **Record enough to reproduce:** date, git revision, config, data/model versions,
  seeds, session ids, artifact hashes, commands, measurements and limits. Keep
  plans, earlier reports and new measurements apart.
- **Report failures and negative results plainly,** with numbers and examples.
  "ML didn't help" is an acceptable result.

## Plan to 19 November: classical obstacle avoidance in the room

The robot drives from a start mark to a goal mark (~3–4 m) in my room, stops or
steers around one or two boxes, and repeated trials are recorded with numbers.
Pose from the board's track speeds (from its encoders) + gyro yaw (dead reckoning).
ML stays after the deadline.

| Week | Deliverable | Done when |
| --- | --- | --- |
| 13–19 Oct | Repo pushed, mount assembled, batteries/PD cable inspected, Jetson on the bank. First contact, then first guarded drive: tracks lifted, then floor. | Stop and 3 s timeout measured (time and distance at the speed cap) in `docs/hardware.md`. |
| 20–26 Oct | `ugv_nav.sensors`, `ugv_nav.recording` (writer, reader, manifest), `teleop` CLI that drives from the keyboard and records camera + feedback. | A recorded drive replays with matching frame counts and feedback events; dropped or stale data is shown; replay cannot send commands. |
| 27 Oct–2 Nov | `ugv_nav.perception`: depth → ground-plane removal → obstacle cells; `ugv_nav.nav.pose`. Tested on replays first. | Obstacles at known distances detected within a stated error; pose error over a 3 m straight run measured with a tape. |
| 3–9 Nov | `ugv_nav.nav.planner` + `drive` CLI: go-to-goal with stop-and-steer. | ≥10 trials, table of success / interventions / time / final position error, failures included. |
| 10–19 Nov | Buffer. README results section, a short GIF, check the owner can explain `guard.py`, `protocol.py`, the planner. | Submitted. |

## Architecture (decided 13 October 2026): plain Python, no ROS

One package, `src/ugv_nav/`; `tools/` and CLIs call into it. ROS 2 would cost weeks
on two OS versions for nothing a reviewer can see.

```
ugv_nav/
  ugv01/        protocol, transport, guard (lease/stop/re-arm), client, sim   [exists]
  sensors/      realsense.py — frames keyed by (number, timestamp), IMU sync
  recording/    writer.py, reader.py, manifest (JSON)
  perception/   obstacles.py — depth → ground plane → obstacle grid
  nav/          pose.py (odometry + gyro), planner.py (go-to-goal, stop/steer),
                loop.py (sense → plan → bounded command at a fixed rate)
  cli/          teleop, record, replay, drive
```

Make units, frame, timestamp, source (hardware or simulation) and validity explicit;
use monotonic time for deadlines. The guard is the only path to the motors; physical
control needs bounded, validated commands, stop priority, and timeout and link-loss
handling. Perception and planning are pure functions over data, so they run the same
on replay and live; replay and simulation never move the robot. Stale sensor data or
pose, and unknown space, are treated as unsafe. One config file per test.

## State

See "Status" in `README.md`; dated history in `docs/log.md`.

## Next steps

1. **Drive check on the floor**, at least 1 m clear ahead: repeat at 0.05 m/s and measure
   stop distance with a tape. Then the 0.10 m/s cap (change `DRIVE_SPEED_M_PER_S`).
   Retry an aborted step with `--steps`. Run command: `docs/hardware.md`.
2. **Before teleop:** find out why 0.78 % of HTTP requests fail, and decide how
   the client treats one failed request. Command a turn to confirm left/right
   mapping. Test a real Wi-Fi loss and reconnect.
3. Find out why the board's pitch reads about +10° on a level robot.
4. **Power:** inspect the PD-to-barrel cable (checks: `docs/hardware.md`, PB205 row),
   then run the Jetson from the bank.
5. Mount the D435i on the robot (needed before recorded drives).
6. For `nav/pose.py`: check the board's track speeds are good enough for dead
   reckoning ([feedback](docs/ugv01-protocol.md#feedback-the-adapter-parses));
   average the gyro at start-up and subtract it, and distrust `r`/`p` after a
   blocking command ([readings](docs/hardware.md#ugv01-first-contact-19-october-2026)).
7. Measure the Jetson case's bottom-hole depth, then tighten the case screws.
8. `sensors/` + `recording/` in parallel.

## After 19 November

Balcony, better pose if needed, then the ML comparison: `docs/plan.md`.
