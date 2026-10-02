# UGV Nav — project notes for Claude

Read this first. Last updated **2 October 2026**. Deeper detail lives in
`README.md`, `docs/plan.md`, `docs/hardware.md`, `docs/reuse.md` and `AGENTS.md`.

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
  file, **this file wins** (those docs predate the decision; trimming them is pending).
- `~/dev/amp` is a **read-only reference**. Its startup, gate and governance
  documents are history, not requirements.
- **Machine access** (IPs, hostnames, users, SSH key paths) is in
  `CLAUDE.local.md`, which is gitignored. Read it when you need to connect to
  something. Never copy those details into tracked files, commits or PRs.
- Don't commit or push unless asked. Keep raw recordings, datasets and weights
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
| **Waveshare UGV01** | ESP32 driver board; JSON commands over UART/USB/Wi-Fi, e.g. `{"T":1,"L":0.5,"R":0.5}`; ~3 s heartbeat auto-stop; encoder motors (speed feedback); onboard 9-axis IMU; 3×18650 in series with built-in UPS/protection board. Firmware is open source (`waveshareteam/ugv_base_general`). Docs: waveshare.com/wiki/UGV01 | No |
| **Batteries** | 3× Molicel P28A flat-top *unprotected* cells — this is the type Waveshare asks for (the UGV's board provides protection). Condition unchecked. | No |
| **Jetson Orin Nano Super 8 GB** | JetPack 7.2.1 / L4T R39.2.1, Ubuntu 24.04 aarch64, CUDA 13.2, boots from Kingston NV3 1 TB NVMe. DisplayPort gave no picture → run headless. Dev kit includes a Wi-Fi card. | Bench (4 Sep); SSH, Wi-Fi, baseline (1 Oct) |
| **RealSense D435i** | USB ID `8086:0b3a`; must enumerate at `5000M` (USB 3). We have **one** suitable USB cable — the camera's own, which was also the Jetson USB-SSH cable. | Stationary, indoor (1 Oct) |
| **Jetson mobile power** | UGREEN PB205 power bank + PD-to-barrel cable (recorded as Adafruit 5451, which requests a fixed 15 V and falls back to 9 V or lower; the 20 V version is 5452 — confirm from the cable's label). Check: the voltage actually negotiated under load (~25 W peak + ~2 W camera), power bank idle shut-off, plug fit (Jetson jack 5.5×2.5 mm). | No |
| **MacBook Pro M4, 48 GB** | Main development, annotation and local ML machine. Repo lives here. | — |
| **ThinkPad P50** | Ubuntu 22.04. Jetson flashing/support host (SDK Manager). Reachable over SSH on the home LAN. | — |

## Done so far

- **Aug 2026 (AMP):** simulated fleet backend + simulated mission (FastAPI/WebSocket).
  Not reused; see `docs/reuse.md`.
- **4 Sep:** Jetson flashed from the P50, boots from NVMe, CUDA smoke test passed,
  USB device-mode SSH worked.
- **29 Sep:** this repo bootstrapped — README, AGENTS.md, docs. No code and no
  git commits at that point.
- **30 Sep:** project review. Decided to put the Jetson on **Wi-Fi** (not an
  Ethernet tether to the P50) so the USB cable is free for the camera and the
  robot can eventually run untethered.
- **30 Sep, blocker found:** SSH P50 → Jetson over USB times out. On the P50,
  `lsusb` shows no NVIDIA device and there is no USB-network interface, so the
  P50 does not see the Jetson over USB at all. Jetson fan spins (it has power);
  whether it fully boots is unknown.
- **1 Oct, blocker resolved:** the USB link works on a different P50 port (cable
  or port was the problem, not the Jetson). Jetson put on the home router by
  Ethernet; key-based SSH from the Mac (`ssh jetson`) and to the P50 (`ssh p50`).
  Baseline re-checked over SSH and unchanged from 4 Sep: Ubuntu 24.04.4, kernel
  `6.8.12-1021-tegra`, L4T 39.2.1, CUDA 13.2, NVMe root (4% used), clean
  `dpkg --audit`, no failed units, 45 °C idle, power mode 25 W. Hostname set (was
  unset), so the Jetson is reachable by its mDNS name (see `CLAUDE.local.md`).
- **1 Oct, Wi-Fi:** Jetson joined the router's 5 GHz network (−28 dBm, 866 Mbit/s
  link); profile is system-wide and autoconnects. Wi-Fi power saving was on; ping
  from the Mac averaged 92 ms via Jetson Wi-Fi vs 21 ms via Jetson Ethernet.
  With power saving disabled in the profile: 20 ms avg via Wi-Fi vs 30 ms via
  Ethernet (20 pings each; remaining jitter is on the Mac's Wi-Fi side).
  **Untethered check passed:** with Ethernet unplugged, SSH via the mDNS name
  works over Wi-Fi; after `sudo systemctl reboot` it rejoined Wi-Fi by itself and
  accepted SSH ~45 s after the reboot command (same address, power saving still
  off, no failed units, 22 ms avg ping).
- **1 Oct, D435i enumeration passed:** camera on its tripod, supplied cable direct
  into a Jetson USB-A port (behind the dev kit's onboard hub). `lsusb` shows
  `8086:0b3a` as Bus 2 Dev 3; `lsusb -t` shows that device at `5000M` (USB 3.2
  descriptor, `bcdDevice 50.f1`). Stock `uvcvideo` binds `/dev/video0–5` and logs
  "Unknown video format" for depth; the IMU appears as generic HID. Expected
  without RealSense kernel patches → use librealsense's RSUSB (libusb) backend.
  Firmware read during the streaming work (below).
- **1 Oct, camera streaming (details in `docs/hardware.md`):** librealsense 2.58.1
  apt packages + pip wheel use the kernel V4L backend: RGB/depth 848×480@30 work,
  but **no IMU** (Jetson kernel lacks HID sensor support). Built 2.58.1 from
  source with **RSUSB** into `~/ugv-nav/opt/librealsense-2.58.1-rsusb`; the
  Jetson venv uses it (PyPI wheel removed). With RSUSB, RGB, depth and IMU work:
  gyro ~200 Hz, accel ~100 Hz, |g| 9.74 m/s². **Start-up behaviour:** depth
  restarts its frame counter at ~0.19 s; IMU samples timestamped seconds before
  the session start arrive first in runs that follow an earlier IMU session
  (origin unconfirmed; also written into recordings); 6–9 gyro and 1–2 accel
  samples were lost in the first 0.15 s in every 1 Oct run, none in the 2 Oct
  checks (cause of the change unknown). Consumers must identify frames by
  (number, timestamp), drop samples timestamped before session start and ignore
  each stream's first ~0.5 s. "Receive − timestamp" includes clock-mapping
  error (IMU values go negative), so it is not a clean latency measure. Camera reports default IMU intrinsics (apparently no stored IMU
  calibration). Firmware was 5.15.1.55 (updated 2 Oct, below). Check tool:
  `tools/realsense_check.py`.
- **1 Oct:** home-network maintenance is pending (details in `CLAUDE.local.md`).
- **2 Oct:** packaged librealsense (V4L) and its 44 helper packages removed, along
  with the RealSense apt repo/key; the camera permission rule now comes from the
  librealsense 2.58.1 source tree on the Jetson (`config/99-realsense-libusb.rules`,
  installed as `/etc/udev/rules.d/99-realsense-libusb.rules`). RSUSB build
  re-verified. Repo commits now use the GitHub noreply address (repo-local
  config). Test area decided: room, then balcony. Learning vault started in
  `vault/` (gitignored, Obsidian).
- **2 Oct, camera firmware 5.15.1.55 → 5.17.3.10:** verified image, flash backup
  first, flashed detached from SSH; tool crashed on exit (code 139) after
  reporting success, but the camera came back normally. Verified after 90 s:
  5.17.3.10, USB 3.2, all sensors, calibration identical, IMU values unchanged.
  Images, backup and logs in `~/ugv-data/firmware/` on the Jetson. **Never
  install firmware ≥ 5.17.4.24 while on SDK 2.58.1.**

## Next steps

1. **IMU calibration** (approved 2 Oct). Waiting on: the owner preparing the box
   (vault task "Prepare the IMU calibration box") and approving `tmux` on the
   Jetson. Procedure and the three tool patches: `docs/hardware.md` → "IMU
   calibration plan". Then record results and verify.
2. Talk to the UGV01 over serial with JSON commands: drive slowly, read encoder
   and IMU feedback, confirm the ~3 s auto-stop (tracks off the ground first).
3. Home-network maintenance (see `CLAUDE.local.md`).
4. Balcony prep and a depth check in balcony light (sun/shade), later.

## Roadmap (detail in `docs/plan.md`)

1. Sensors working on the Jetson (camera streams + recording).
2. Small typed Python adapter for UGV01 commands and feedback.
3. Record and replay: one capture tool, a manifest, a replay reader.
4. Classical autonomy: depth-based obstacles + a pose source + route following.
   Pose options: visual-inertial odometry (e.g. NVIDIA cuVSLAM, RTAB-Map),
   wheel encoders + IMU, or AprilTags. **Localization is the likely schedule
   sink — pilot it early.**
5. ML: visual traversability. Ideas: self-supervised labels from where the robot
   actually drove + depth-confirmed obstacles; frozen pretrained features
   (DINOv2-style) with a small head; hand-label only the frozen test set.
   The test area needs places where geometry alone fails (flat no-go regions such
   as a rug edge indoors, or mats, plant soil and drains on the balcony) —
   otherwise ML has nothing to win.
6. Deploy on the Jetson; run matched routes with ML off vs on.

## Open notes

- ROS 2 is optional. If adopted: Jetson (Ubuntu 24.04) → **Jazzy**; the P50 on
  22.04 would mismatch (Humble), so upgrade it or use a container.
- `AGENTS.md`, `docs/plan.md` and `docs/hardware.md` are wordier and more
  safety-heavy than wanted; trim them when convenient.
