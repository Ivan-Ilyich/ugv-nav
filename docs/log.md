# Project log

Dated history, newest at the bottom. Current state: `README.md`; measurements:
`docs/hardware.md`.

- **24 Aug (AMP):** the P50 ran the simulated fleet backend of AMP, a mowing startup
  idea (FastAPI/WebSocket; 55 packets, not real telemetry). AMP was dropped on
  1 Sep; its hardware carried over, its code was not reused ([assessment](reuse.md)).
- **4 Sep:** Jetson flashed from the P50; boots from NVMe; CUDA smoke test passed;
  USB device-mode SSH worked. Only one suitable USB cable, so Ethernet SSH was
  proposed to keep it free for the camera.
- **29 Sep:** repo started (README, AGENTS.md, docs); all equipment available.
- **30 Sep:** decided to put the Jetson on **Wi-Fi**, not an Ethernet tether to the
  P50, so the USB cable is free for the camera and the robot can run untethered.
  SSH from the P50 over USB timed out (no NVIDIA device in the P50's `lsusb`).
- **1 Oct:** USB SSH works on a different P50 port. Jetson on the home router by
  Ethernet, then Wi-Fi, with key-based SSH (`ssh jetson`, `ssh p50`); fresh SSH
  without a cable survives a reboot; D435i enumerates at USB 3
  ([results](hardware.md#checkpoint-usb-independent-ssh-then-d435i-enumeration)).
  Baseline re-checked unchanged with `date -u`, `cat /etc/os-release`, `uname -r`,
  `head -n 1 /etc/nv_tegra_release`, `dpkg-query -W nvidia-l4t-core`,
  `findmnt -no SOURCE,FSTYPE,TARGET /`, `df -h /`, `/usr/local/cuda/bin/nvcc --version`,
  `dpkg --audit`, `apt-get -s check` and `systemctl --failed --no-pager`.
- **1 Oct, camera:** the packaged SDK 2.58.1 (V4L) streams RGB and depth but no IMU;
  a source build with RSUSB streams all three
  ([results](hardware.md#streaming-setup-follows-enumeration)).
- **1 Oct, RSUSB build:** tag `v2.58.1` (commit `bf2778061d5d`), configured with
  `-DCMAKE_BUILD_TYPE=Release -DFORCE_RSUSB_BACKEND=ON -DBUILD_PYTHON_BINDINGS=ON
  -DPYTHON_EXECUTABLE=<venv>/bin/python -DBUILD_WITH_CUDA=OFF -DBUILD_WITH_DDS=OFF
  -DBUILD_EXAMPLES=OFF -DBUILD_GRAPHICAL_EXAMPLES=OFF -DBUILD_TOOLS=ON
  -DBUILD_UNIT_TESTS=OFF` (configure downloads pybind11), with `CMAKE_INSTALL_PREFIX`,
  `CMAKE_INSTALL_RPATH` (`<prefix>/lib`) and `PYTHON_INSTALL_DIR` inside the prefix
  `~/ugv-nav/opt/librealsense-2.58.1-rsusb`. Binaries find their library through
  `RUNPATH`; an `LD_LIBRARY_PATH` would override it. ~12 min at `-j4`, temperature
  not monitored. The Python link failed once, cause unknown, and passed on a `-j1`
  rebuild (spot readings ≤ 48 °C during the link steps). Tool environment:
  `/usr/bin/python3 -m venv ~/ugv-nav/.venv` (Python 3.12.3) with `numpy` 2.5.3 and
  a `.pth` file pointing at `<prefix>/lib/python3.12/site-packages` (PyPI wheel
  removed). RSUSB needs the RealSense udev rules: from the `librealsense2-udev-rules`
  package on 1 October, from the source tree's file since 2 October (below).
- **1 Oct, Jetson changes:** hostname set; Wi-Fi profile added (autoconnect, power
  saving off); RealSense apt repository and key added
  (`/etc/apt/sources.list.d/librealsense.list`, `/etc/apt/keyrings/librealsenseai.gpg`);
  `librealsense2`, `-gl`, `-utils` and `-udev-rules` 2.58.1 held, with 45 automatic
  packages (GTK/X11/Mesa, `v4l-utils`, `at`). Build dependencies: `libusb-1.0-0-dev`,
  `libssl-dev`, `pkg-config` (`git`, `python3.12-dev` already present). Upgraded as
  dependencies: Mesa, GLib, bzip2, Python 3.12 (`3.12.3-1ubuntu0.17`), OpenSSL; no
  L4T, CUDA or kernel package changed. Source tree `~/src/librealsense-2.58.1`;
  11 recordings (6.1 GB) in `~/ugv-data/recordings`.
- **2 Oct:** packaged SDK removed. The source tree's
  `config/99-realsense-libusb.rules` installed as
  `/etc/udev/rules.d/99-realsense-libusb.rules` (covers the D435i and its
  firmware-recovery IDs); the 4 packages purged with `--autoremove` (48 in all: 44 of
  the 45 automatic ones; `gir1.2-glib-2.0-dev` stays); apt repository and key
  removed; `dpkg --audit` clean; all three sensors show. Udev rules reach a connected
  camera only after `sudo udevadm control --reload-rules && sudo udevadm trigger
  --subsystem-match=usb --attr-match=idVendor=8086 && sudo udevadm settle`. Test
  area decided: room, then balcony.
- **2 Oct, camera firmware 5.15.1.55 → 5.17.3.10:** device report, calibration dump
  (`rs-enumerate-devices -c`) and a 5 s check saved; backup with `rs-fw-update -b`;
  flashed with `rs-fw-update -f <image>`, detached from SSH, 08:12:20–08:12:53 UTC.
  It printed "successfully updated to FW: 5.17.3.10", then crashed on exit (code 139,
  segmentation fault); the camera had already reconnected normally
  ([details](hardware.md#streaming-setup-follows-enumeration)).
- **2 Oct:** 20-minute soak with CPU alignment, no lost frames
  ([results](hardware.md#soak-test-2-october-2026)).
- **2 Oct, UGV01 groundwork (no hardware):** protocol researched from firmware source
  ([notes](ugv01-protocol.md)); adapter in `src/ugv_nav/ugv01/` with a simulator;
  111 tests; read-only probe `tools/ugv01_probe.py` (not run).
- **4–12 Oct:** Jetson case assembled; boots and answers SSH. Bank confirmed as
  UGREEN PB205. Printed mount designed; PETG print ordered 12 Oct. IMU calibration
  deferred (9 Oct).
- **13 Oct:** Hull confirmed that a public GitHub repo with a README is acceptable
  evidence of Python programming for the MSc application. Decided: classical
  obstacle avoidance in the room by 19 Nov; plain Python, no ROS.
- **19 Oct:** mount assembled ([mount](../hardware/jetson-bank-mount/README.md)). It
  covers the Jetson's 40-pin header, so the Jetson–UGV01 link is **Wi-Fi/HTTP**.
  First contact passed from the Mac on the board's access point; then the board
  joined the home 2.4 GHz network (`T:407`, AP password changed). Added
  `HttpTransport` and `--http` (134 tests). Probe from the Jetson and tilt check
  passed ([results](hardware.md#ugv01-first-contact-19-october-2026)).
- **23 Oct:** ruff clean across the repo (`uv run ruff check .`).
- **6 Nov:** `tools/ugv01_drive_check.py` written, with 47 new tests, and checked
  against a fake board on localhost. **First guarded drive** (tracks lifted,
  0.05 m/s): host stop, lease stop and firmware heartbeat measured; one Wi-Fi
  timeout aborted the first step c try safely, and `--steps` was added to retry it
  ([results](hardware.md#first-guarded-drive-6-november-2026)).
