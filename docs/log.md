# Project log

Dated history, newest at the bottom. `CLAUDE.md` holds the current state;
measurements are in `docs/hardware.md`.

## September–October 2026

- **Aug 2026 (AMP):** simulated fleet backend and mission (FastAPI/WebSocket). Not
  reused; see `docs/reuse.md`.
- **4 Sep:** Jetson flashed from the P50, boots from NVMe, CUDA smoke test passed,
  USB device-mode SSH worked.
- **29 Sep:** repo started: README, AGENTS.md, docs. No code or commits yet.
- **30 Sep:** decided to put the Jetson on **Wi-Fi**, not an Ethernet tether to the
  P50, so the USB cable is free for the camera and the robot can run untethered.
- **30 Sep, blocker:** SSH P50 → Jetson over USB timed out. `lsusb` on the P50
  showed no NVIDIA device. The Jetson fan spun; whether it booted was unknown.
- **1 Oct, blocker resolved:** USB works on a different P50 port. Jetson on the home
  router by Ethernet, with key-based SSH (`ssh jetson`, `ssh p50`). Baseline
  unchanged, before that day's package changes: Ubuntu 24.04.4, kernel `6.8.12-1021-tegra`, L4T 39.2.1, CUDA 13.2, NVMe
  root (4% used), clean `dpkg --audit`, no failed units, 45 °C idle, 25 W mode.
- **1 Oct, Wi-Fi:** joined the 5 GHz network (−28 dBm, 866 Mbit/s link). Power saving
  on: ping from the Mac 92 ms via Wi-Fi, 21 ms via Ethernet. Off: 20 ms against
  30 ms (20 pings each). **Untethered check passed:** after `sudo systemctl reboot`
  it rejoined Wi-Fi by itself and accepted SSH ~45 s later (22 ms avg ping).
- **1 Oct, D435i enumeration passed:** `8086:0b3a`, Bus 2 Dev 3, at `5000M` (USB 3.2
  descriptor, `bcdDevice 50.f1`). Stock `uvcvideo` binds `/dev/video0–5` and logs
  "Unknown video format" for depth, so use librealsense's RSUSB backend.
- **1 Oct, camera streaming:** apt 2.58.1 + pip wheel (V4L): RGB/depth 848×480@30,
  **no IMU**. Built 2.58.1 from source with **RSUSB**: RGB, depth and IMU work, gyro
  ~200 Hz, accel ~100 Hz, |g| 9.74 m/s². Depth restarts its frame counter at ~0.19 s;
  in runs that follow an earlier IMU session, samples stamped before the session arrive
  first (origin unconfirmed; also written into recordings); 6–9 gyro and 1–2 accel samples
  were lost in the first 0.15 s on 1 Oct, none on 2 Oct (cause unknown). Check tool:
  `tools/realsense_check.py`.
- **1 Oct:** home-network maintenance pending (see `CLAUDE.local.md`).
- **2 Oct:** packaged librealsense and its 44 helper packages removed, with the
  RealSense apt repo and key. Commits now use the GitHub noreply address (repo-local
  config). Test area decided: room, then balcony. Learning vault started in `vault/`
  (gitignored, Obsidian).
- **2 Oct, camera firmware 5.15.1.55 → 5.17.3.10:** flashed after a backup; the tool
  crashed on exit (code 139) but the camera came back normally. Files in
  `~/ugv-data/firmware/`. **Never install firmware ≥ 5.17.4.24 on SDK 2.58.1.**
- **2 Oct, Jetson soak:** 20 min of streaming with CPU alignment: no lost frames,
  48 → 50 °C, ~5.2 W (`tools/jetson_soak.py`).
- **2 Oct, UGV01 groundwork (no hardware):** protocol researched from firmware source
  (`docs/ugv01-protocol.md`); adapter in `src/ugv_nav/ugv01/` (speed cap 0.10 m/s,
  0.5 s lease, stop priority, re-arm) with a simulator; 111 tests; read-only probe
  `tools/ugv01_probe.py` (not run).
- **4–12 Oct:** Jetson case assembled with the Wi-Fi antennas on the card (socket 1
  Main, 2 Aux); boots and answers SSH. Bank confirmed as UGREEN PB205 (90597A).
  Printed mount designed; PETG print ordered 12 Oct. IMU calibration deferred (9 Oct).
- **13 Oct:** Hull confirmed that a public GitHub repo with a README is acceptable
  evidence of Python programming for the MSc application (deadline 19 Nov). Decisions:
  target classical obstacle avoidance in the room; plain Python, no ROS; push now, go
  public at the first measured drive (5 Nov at the latest); keep `CLAUDE.md` and
  `AGENTS.md` short.
- **19 Oct:** mount assembled with the kit's own T-nuts (case screws hand-snug). It
  covers the 40-pin header, so the Jetson–UGV01 link is **Wi-Fi/HTTP** (`/js`
  endpoint). **First contact passed** from the Mac: `T:130` returned `T:1001`
  (11.82 V, level), `T:126` returned IMU data; gyro z offset ≈ 4.0 at rest,
  magnetometer inactive.
- **19 Oct, later:** board joined the home 2.4 GHz network (`T:407`, AP password
  changed); HTTP round trip 18–50 ms, median 19 ms. Added `HttpTransport` and `--http`
  (134 tests).
- **19 Oct, afternoon:** **probe passed from the Jetson**: 14 requests, 0 failed, 10
  valid `T:1001`, median ≈ 18 ms (max 101 ms), 11.52 V. **Tilt check:** roll/pitch
  match the accelerometer within 0.24° (r ≈ −1.5°, p ≈ −0.1°); the −20°/−26° after
  `T:407` was transient. Gyro z varies −1.8 to +4.0 between samples, so the "offset
  ≈ 4.0" was noise.
- **6 Nov:** `tools/ugv01_drive_check.py` written, with 47 new tests, and checked
  against a fake board on localhost.
- **6 Nov, first guarded drive (tracks lifted, 0.05 m/s):** host stop and lease stop
  0.26 s, firmware heartbeat 3.26 s after the last `T:1`; `T:130` polling did not
  refresh it. 0.78 % of HTTP requests failed, and one aborted the first step c try
  safely. Not yet on the floor.
