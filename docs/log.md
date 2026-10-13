# Project log

Dated record of what was done, with results and limits. Newest entries at the
bottom. `CLAUDE.md` keeps only the current state; this file keeps the history.
Detailed measurements live in `docs/hardware.md`.

## September–October 2026

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
- **2 Oct, Jetson soak:** 20 min of full camera streaming with CPU alignment of
  every frame: no lost frames, 48 → 50 °C, ~5.2 W (`tools/jetson_soak.py`).
- **2 Oct, UGV01 groundwork (no hardware):** protocol researched from the firmware
  source and docs (`docs/ugv01-protocol.md`); adapter in `src/ugv_nav/ugv01/`
  (speed cap 0.10 m/s, 0.5 s command lease, stop priority, explicit re-arm after
  any fault) with a simulator; 111 tests, mypy strict and ruff clean via `uv`;
  read-only probe `tools/ugv01_probe.py` (not run).

- **4–12 Oct:** Jetson case (Waveshare JETSON-ORIN-CASE-A) assembled with the
  Wi-Fi antennas on the card (socket 1 Main, 2 Aux); the Jetson boots in it and
  answers SSH. Power bank confirmed from its label as UGREEN PB205 (90597A).
  A two-part printed mount (`hardware/jetson-bank-mount/`) was designed to stack
  the bank and the case on the UGV01's rails; PETG print ordered 12 Oct.
  IMU calibration deferred (9 Oct) — the neutral table is good enough for now.
- **13 Oct:** Hull confirmed that a public GitHub repo with a README is
  acceptable evidence of Python programming for the MSc application (deadline
  19 Nov). Decisions: target classical obstacle avoidance in the room by then;
  plain Python package, no ROS; push now, go public at the first measured
  drive (5 Nov at the latest); keep `CLAUDE.md`/`AGENTS.md` but short.
