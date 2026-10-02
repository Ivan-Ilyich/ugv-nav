# Hardware baseline

Reconciled on **29 September 2026** from earlier reports; no device was
contacted during that bootstrap. Commissioning results from **1–2 October 2026**
are recorded under the checkpoint and streaming sections below. This is a
sanitized summary; raw outputs stay outside the repository.

## Evidence and chronology

- **24 August 2026 inventory:** recorded component receipt separately from
  testing; still listed the NVMe, power bank, and charger as in transit.
- **24 August 2026 host report:** the P50 ran the simulated Python backend and
  received 55 WebSocket packets. This establishes a reported host/application
  check, not physical telemetry.
- **4 September 2026 bench evidence:** the commissioning report and matching
  operator-posted terminal outputs record Jetson NVMe boot, package/service
  checks, and CUDA execution. These outputs were inspected on 29 September.
  The report also describes installation screenshots and hardware photographs;
  those attachments were not independently revalidated here.
- **Commissioning exchange, 4 September 2026:** only one suitable USB cable was
  available. Ethernet SSH was proposed to free it for the D435i. As of
  29 September no later Ethernet result or camera enumeration had been found.
- **29 September 2026 owner inventory:** all equipment in the README is stated
  as available. This supersedes old delivery labels, not missing functional tests.
- **1 October 2026 commissioning:** USB-independent SSH (home router, then
  Wi-Fi), D435i enumeration and stationary streaming; results below.
- **2 October 2026:** packaged camera SDK removed, camera firmware updated to
  5.17.3.10, IMU calibration planned; results below.

The source checkout's inventory/evidence register has not incorporated the
September Jetson results. It remains unchanged. The original conversation,
photographs, purchase records, and network identifiers remain outside this repo.

## Status

Reconciled on 29 September; rows updated with the 1–2 October results.

| Component | Best available evidence | What remains open |
| --- | --- | --- |
| Jetson Orin Nano Super 8 GB | Reported stationary bench pass, 4 September; software baseline re-checked over SSH, 1 October | Sustained load, enclosure cooling, navigation workloads |
| Kingston NV3 1 TB (`SNV3S/1000G`) | Reported installed root filesystem and normal cold boot, 4 September | Storage endurance/performance and capture workload not measured |
| Official Jetson PSU and stock fan | Bench report identifies Lite-On `PA-1450-26`, 19 V / 2.37 A; fan operated | Retest current arrangement before relying on historical configuration |
| P50 | Ubuntu 22.04 x86_64 and SDK Manager used in September report; reachable by SSH on the home network, 1 October | Package state not inventoried |
| Jetson network access | Key-based SSH over Wi-Fi with Ethernet and USB networking disconnected, surviving a reboot; USB device-mode SSH from the P50 works on one P50 port (1 October) | Wi-Fi range and robustness away from the router and on the moving robot |
| D435i (`999AFR` kit) | USB 3 enumeration; stationary indoor RGB/depth streaming (V4L and RSUSB) and IMU (RSUSB only), 1 October; firmware updated 5.15.1.55 → 5.17.3.10, 2 October | IMU calibration, depth quality in balcony light, rover mount |
| UGV01 stock controller/drivetrain | Available; no physical test artifact located | Controller/firmware identity, transport/protocol, feedback, bounded control, stopping and watchdog |
| Three Molicel P28A cells | Available; earlier inventory identifies flat-top unprotected cells | Condition, approved installation/charging and actual pack use |
| PB205 / X553 / PD-to-barrel cable | Available; cable previously identified as Adafruit 5451 | Exact assembled power path, negotiated output, fit/polarity, load and runtime checks |
| Jetson enclosure | Available; earlier inventory identifies Waveshare 25334 | Assembly, mounting, thermal behavior; bundled CSI bracket reported not to fit D435i |
| MacBook Pro M4 / 48 GB | Owner-provided development-machine inventory | ML environment and experiment runtime not benchmarked |

The mini tripod is suitable for the proposed stationary camera check; it does
not establish a secure rover mount. No GNSS, lidar, working wheel odometry, or
localization system is established by this inventory.

## Previously reported Jetson configuration

These are **4 September observations**, not an instruction to reinstall or upgrade:

| Item | Reported value |
| --- | --- |
| Flash host/tool | P50, Ubuntu 22.04; SDK Manager `2.4.1-13536` |
| Installed release | JetPack `7.2.1`; Jetson Linux `R39.2.1` |
| OS / kernel | Ubuntu `24.04.4` aarch64 / `6.8.12-1021-tegra` |
| BSP package | `nvidia-l4t-core 39.2.1-20260806224157` |
| Root filesystem | `/dev/nvme0n1p1`, ext4, before and after normal cold boot |
| CUDA compiler | CUDA `13.2`, `nvcc V13.2.86` |
| CUDA execution | `CUDA kernel smoke: PASS \| Orin \| CC 8.7 \| value=42` |
| Package/services | Empty `dpkg --audit`; successful `apt-get -s check`; no failed systemd units |

The umbrella `nvidia-jetpack` package was absent. A simulated install proposed
16 metapackages; this alone is not a reason to repair the machine and does not
functionally validate cuDNN, TensorRT, VPI, or OpenCV. Five idle telemetry samples
around 48.5–50.3 °C and 4.49–4.53 W do not establish sustained thermal or power
performance. DisplayPort-to-HDMI produced no signal before flashing and was not
retested; the cause is unresolved and headless commissioning can continue.

NVIDIA's [Orin Nano guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/quick_start.html)
currently documents the JetPack 7.2.1 / L4T r39.2.1 pairing (checked 29 September
2026). That confirms the reported pairing is supported, not what is installed
on the device today.

## Reproducible inspection notes

The baseline commands below were re-run on 1 October (result under the
checkpoint). Keep raw output locally; redact user/host names, addresses, MACs,
device serials, and network-profile names before adding a short result here.

### Recheck the Jetson baseline

On the Jetson, using an already verified session:

```bash
date -u
cat /etc/os-release
uname -r
head -n 1 /etc/nv_tegra_release
dpkg-query -W nvidia-l4t-core
findmnt -no SOURCE,FSTYPE,TARGET /
df -h /
/usr/local/cuda/bin/nvcc --version
dpkg --audit
apt-get -s check
systemctl --failed --no-pager
```

These inspect versions, storage, and package health. They do not rerun the CUDA
kernel. The earlier smoke source/binary was temporary; no durable standalone
artifact was located in the inspected source files. A future GPU regression
check should retain its source and sanitized output together.

### Checkpoint: USB-independent SSH, then D435i enumeration

Planned procedure (the result below records the route actually taken). Use the
previously tested official Jetson supply and stock cooling, with the robot
stationary and drivetrain uninvolved.

1. Keep the working USB connection attached. Connect the existing Ethernet cable
   between P50 and Jetson. A direct link does not by itself guarantee an IPv4
   address; inspect both ends before selecting a connection configuration.
2. On the **P50 local terminal**:

   ```bash
   nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
   ip -4 route
   ```

3. On the **Jetson through existing USB SSH**:

   ```bash
   nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
   ip -4 -br address
   ```

4. In that commissioning task, identify/configure the Ethernet link from those
   results. Record actual addresses/profiles only in ignored local notes. Open a
   second SSH session to the Ethernet address; verify its server address and
   route use the Ethernet interface. Keep a recovery path until this succeeds.
5. Disconnect USB only after that independent session works. Confirm the
   Ethernet session remains usable and a fresh SSH connection succeeds.
6. Put the D435i securely on its mini tripod. Connect its supplied cable directly
   to the Jetson USB-A port, with USB-C at the camera; use no hub/extension.
7. On the Jetson:

   ```bash
   lsusb -d 8086:0b3a
   lsusb -t
   ```

**Completion:** fresh SSH works with USB networking disconnected, and the D435i
appears as `8086:0b3a` with its matching USB-tree device at `5000M`. Match the
bus/device numbers; another device at `5000M` is not a pass. `480M` is a USB 2
fallback. Record date, commands, sanitized observations, and any failure.

Stop this checkpoint at enumeration. Streaming is the next separate check;
enumeration proves neither image quality nor SDK compatibility.

**Result, 1 October 2026 — passed, with one change of route.** The P50 USB link
had failed on 30 September; it worked again on a different P50 port. Instead of a
direct P50 cable, the Jetson was put on the home router (Ethernet, then Wi-Fi):

- Software baseline re-checked over SSH, unchanged from 4 September (versions in
  the table above), before that day's package changes (listed at the end of this
  file); no failed units; idle 45 °C; power mode 25 W.
- With Ethernet and USB networking disconnected, fresh SSH over Wi-Fi works and
  survives a clean reboot (back in ~45 s). Wi-Fi power saving was disabled: 20
  pings from the Mac averaged 92 ms via the Jetson's Wi-Fi against 21 ms via its
  Ethernet, and 20 ms via Wi-Fi afterwards.
- D435i on the supplied cable, directly in a Jetson USB-A port: `lsusb` shows
  `8086:0b3a` as Bus 2 Device 3, and `lsusb -t` shows that device at `5000M`.
  Stock `uvcvideo` binds it and reports unknown depth formats; the IMU appears
  as generic HID. Firmware is read in the streaming section.

Limits: Wi-Fi measured only at short range in one room; temperatures and pings
are spot readings from session commands, not logged.

### Streaming setup follows enumeration

Select a pinned librealsense version/backend for the verified OS, kernel,
architecture, and camera firmware. The upstream
[Jetson installation guide](https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md)
distinguishes native kernel and RSUSB backends. Consult the release-specific
support information before installing; a working JetPack/CUDA setup alone does
not validate the camera stack. Do not apply an old kernel patch or firmware
upgrade by assumption.

Record stream profiles, SDK/backend/firmware versions, RGB/depth calibration,
depth scale, frame/timestamp behavior and IMU availability. Run a fixed stationary
capture window and report observed frame rate, gaps, invalid-depth fraction, and
any drops. Repeat with representative balcony lighting before choosing the
perception task. Retain a replayable sample outside Git and a sanitized manifest.

**Result, 1 October 2026 — packaged SDK (V4L backend): RGB and depth only.**

- SDK: librealsense **2.58.1**, the latest non-beta release (2.58.2–2.58.4 are
  betas). Its release notes list Jetson support for JetPack 5.0.2, 6.0–6.2 and
  7.0; the installed JetPack 7.2.1 is not listed, so compatibility here rests on
  the checks below. Installed from the RealSense apt repository (`noble`,
  arm64), pinned and held at `2.58.1-0~realsense.8236`, plus
  `pyrealsense2==2.58.1.10581` from PyPI. Both use the **kernel V4L backend**
  (the process opens `/dev/video*`).
- Camera firmware **5.15.1.55**; the 2.58.1 release notes list ≥ 5.17.3.10 for
  the D435i. Not updated that day (updated 2 October, below).
- Check with an earlier version of `tools/realsense_check.py` (it identified
  frames by number only and replayed through the pipeline; superseded):
  stationary indoor scene, 848×480 @ 30 fps depth (Z16) + RGB8, 10 s. Depth 284
  and colour 287 frames delivered, 29.98 fps each, no frame-number gaps,
  intervals 33.4 ms median / 33.7 ms max; receive time minus timestamp ≈ 36 ms
  median (colour max 134 ms, at start-up); global time domain with
  sensor-timestamp metadata; depth scale 1 mm; invalid depth 18.7 % median
  (43 % max). Depth-to-colour offset 15 mm. The recording (ROS 2 `.db3`,
  ~590 MB per 10 s) holds 292 depth frames against 284 delivered: frames
  0–6, then a frame-counter restart at 1 about 0.40 s in, then 285 more.
- **No IMU with V4L:** the Jetson kernel is built without HID sensor support
  (`CONFIG_HID_SENSOR_HUB` not set), so no Motion Module appears.

**Result, 1 October 2026 — source build with RSUSB: RGB, depth and IMU.**

Source tag `v2.58.1` (commit `bf2778061d5d`), configured with
`-DCMAKE_BUILD_TYPE=Release -DFORCE_RSUSB_BACKEND=ON -DBUILD_PYTHON_BINDINGS=ON
-DPYTHON_EXECUTABLE=<venv>/bin/python -DBUILD_WITH_CUDA=OFF -DBUILD_WITH_DDS=OFF
-DBUILD_EXAMPLES=OFF -DBUILD_GRAPHICAL_EXAMPLES=OFF -DBUILD_TOOLS=ON
-DBUILD_UNIT_TESTS=OFF` (configure fetches pybind11 and other third-party
sources from the network), with `CMAKE_INSTALL_PREFIX`, `CMAKE_INSTALL_RPATH`
(`<prefix>/lib`) and `PYTHON_INSTALL_DIR` all inside the user-owned prefix
`~/ugv-nav/opt/librealsense-2.58.1-rsusb`. Its binaries find their library
through `RUNPATH`, so they do not load the packaged V4L library of the same
soname in normal use (an `LD_LIBRARY_PATH` pointing elsewhere would override
this). Compiling took ~12 min at `-j4`. The Python module link then failed once
(cause not established; an earlier, interrupted build had been running in the
same tree) and succeeded on a `-j1` rebuild. Temperature was not monitored
during the `-j4` compile; spot readings during the later link steps were ≤ 48
°C.

Tool environment on the Jetson: `/usr/bin/python3 -m venv ~/ugv-nav/.venv`
(Python 3.12.3) with `numpy` 2.5.3, and a `.pth` file in the venv's
site-packages pointing at `<prefix>/lib/python3.12/site-packages` (the PyPI
wheel was removed). RealSense udev rules are needed for libusb access (on 1 October from
`librealsense2-udev-rules`; since 2 October from the source tree's
`config/99-realsense-libusb.rules`, below); they applied to the already-connected camera
only after `sudo udevadm control --reload-rules && sudo udevadm trigger
--subsystem-match=usb --attr-match=idVendor=8086 && sudo udevadm settle`.

Results with the corrected tool (an earlier, uncommitted version, sha256
`a42d1faf1eeb…`; later revisions changed only replay-completion reporting,
overwrite protection, empty-stream reporting, the mean-rate calculation and a
filter for samples stamped far in the future):
three 10 s trials with `--record`, 20:24–20:25 UTC, same stationary scene. The
process opens only `/dev/bus/usb/*`. Default profiles: depth and colour
848×480@30, gyro 200 Hz, accel 100 Hz.

| Per trial (3 trials) | Depth | Colour | Gyro | Accel |
| --- | --- | --- | --- | --- |
| Distinct frames received | 287 | 287–288 | 1997–1999 | 1010–1011 |
| Same frame delivered twice | 0–1 | 0 | 0 | 0 |
| Timestamped before session start | 0 | 0 | 7–8 | 3–4 |
| Missing frame numbers | 0 | 0 | 6–9 | 1–2 |
| Frame-counter resets | 1, at 0.18–0.19 s | 0 | 0 | 0 |
| Longest interval (when) | 175–191 ms (the reset) | ≤ 34.3 ms | 35–50 ms (0.08 s) | 20–30 ms (0.14 s) |
| Mean rate over the window | 29.5–29.6 fps | 30.0 fps | 199.4–199.8 Hz | 100.3 Hz |
| Receive − timestamp, median (min) | 34–35 ms (15–22) | 35 ms (15–22) | −0.3 to 0.1 ms (−20 to −13) | −0.3 to 0.1 ms (−20 to −13) |
| Frames in the recording | 292–293 | as received | as received | as received |

- **Depth start-up:** the camera emits a few frames, restarts its frame counter
  at 0 about 0.18–0.19 s after the first delivered frame, and the pipeline
  passes on only the last pre-restart frame; the other 4–5, and the session's
  final frame, are only in the recording. After the restart the stream is
  continuous. The V4L run showed the same kind of restart (at 1, after 0.40 s).
- **IMU start-up:** samples with global timestamps about 5 s to 1 min before the
  session start arrive first; their frame numbers continue directly into the
  session's. They appeared in every RSUSB run except the first (which had no
  earlier IMU session); their origin is unconfirmed.
  Separately, 6–9 gyro and 1–2 accel samples are missing around 0.06–0.14 s and
  were never delivered (the recordings have the same holes).
- **Receive − timestamp** includes the SDK's device-to-host clock-mapping
  error (at least 13–20 ms at times, shown by the negative IMU values), so it is
  not a clean latency measurement.
- **IMU at rest:** |accel| = 9.743–9.745 m/s² (≈ 0.7 % below 9.81); gyro mean
  ≈ 0.002 rad/s. The camera reports default IMU intrinsics (identity scale,
  zero bias and variances), i.e. apparently no stored IMU calibration.
- Seven earlier RSUSB runs that day used earlier tool versions that identified
  frames by number only. They showed the same patterns, but their depth gap,
  duplicate and recorded-versus-delivered counts were counting artifacts and
  are superseded by this table.

Implications: identify frames by (number, timestamp), drop samples timestamped
before a session starts, and ignore the first ~0.5 s of each stream, counted
from its first non-stale sample (≈ 1 s after pipeline start here). The packaged
V4L build was removed on 2 October (below); the venv's `pyrealsense2` is the
RSUSB build.

**System changes on the Jetson, 1 October 2026** (for reproducibility and cleanup):

- Hostname set (was unset); Wi-Fi profile added (autoconnect, power saving off).
- RealSense apt repository and key added (`/etc/apt/sources.list.d/librealsense.list`,
  `/etc/apt/keyrings/librealsenseai.gpg`); `librealsense2`, `-gl`, `-utils`
  and `-udev-rules` 2.58.1 installed and held, pulling in 45 automatic
  packages (GTK/X11/Mesa development libraries, `v4l-utils`, `at`).
- Build dependencies newly installed: `libusb-1.0-0-dev`, `libssl-dev`,
  `pkg-config` (`git` and `python3.12-dev` were already present; the latter was
  upgraded with Python 3.12 below).
- Upgraded as dependencies (Ubuntu updates): Mesa, GLib, bzip2, Python 3.12
  (`3.12.3-1ubuntu0.17`), OpenSSL. No NVIDIA L4T, CUDA or kernel package changed.
- Source and build tree `~/src/librealsense-2.58.1`; install prefix as above;
  venv `~/ugv-nav/.venv`; 11 recordings (6.1 GB) in `~/ugv-data/recordings`.

**Cleanup, 2 October 2026 — packaged SDK removed.** Installed the source tree's
`config/99-realsense-libusb.rules` as `/etc/udev/rules.d/99-realsense-libusb.rules`
(it covers the D435i and its firmware-recovery product IDs), then purged
`librealsense2`, `-gl`, `-utils` and `-udev-rules` with `--autoremove`: 48
packages, i.e. those 4 plus 44 of the 45 automatic dependencies
(`gir1.2-glib-2.0-dev` stays because another package now needs it). Removed the
RealSense apt repository and key. Afterwards `dpkg --audit` is clean, the RSUSB
build has no missing libraries, and the camera shows all three sensors.

Two 4 s checks after the cleanup: gyro 200.4–200.5 Hz and accel 100.6 Hz, each
with 9 gyro and 3 accel samples timestamped before the start and **no** missing IMU
samples; the 5 s and 10 s firmware checks below had none either, whereas every
1 October RSUSB run had some. What changed between the days is not established.
One earlier 4 s run reported no mean IMU rate: its first kept timestamp was not
earlier than its last, and it kept 3 accel and 11 gyro samples more than the next
two runs, so its start-up samples were probably stamped at or after the run's
end and passed the stale filter. Not reproduced; the tool now also drops global
timestamps more than 1 s ahead of their arrival (`future_stamped`).

**Firmware update, 2 October 2026 — 5.15.1.55 → 5.17.3.10.**

- Image `D4XX_FW_Image-5.17.3.10.bin` from RealSense's SDK firmware mirror (the
  address the SDK's own update check uses; the same version is on the official
  download page behind a licence agreement): 1,573,660 bytes, SHA-256
  `4c347e3a…e4d2`, embedded version 5.17.3.10. Rollback image
  `D4XX_FW_Image-5.15.1.0.bin` (RealSense lists 5.15.1.55 as equal to
  5.15.1.0): SHA-256 `29bd3181…7028`. Both are under the RealSense firmware
  licence and are kept with the logs in `~/ugv-data/firmware/` (not in Git).
- Before: camera idle (no process held its USB node), USB 3 (`5000M`); device
  report, calibration dump (`rs-enumerate-devices -c`) and a 5 s check saved.
  Flash backup with `rs-fw-update -b` on its own: 2,097,152 bytes. It archives
  the calibration and device data; a locked camera cannot be flashed back from it.
- Flash: `rs-fw-update -f <image>`, run detached from the SSH session,
  08:12:20–08:12:53 UTC. The tool printed "successfully updated to FW:
  5.17.3.10" and then crashed on exit (code 139, segmentation fault); the camera
  had already reconnected normally (`8086:0b3a`, USB 3, not recovery mode).
- After 90 s: `rs-fw-update -l` and the device report show 5.17.3.10, USB 3.2
  and all three sensors. The calibration dump is identical apart from the USB
  device number. A 10 s check shows identical depth, colour and IMU intrinsics
  and depth-to-colour extrinsics, unchanged rates (gyro 200.4 Hz, accel
  100.6 Hz, depth 29.6 fps, colour 30.0 fps), no missing frames, gyro at rest
  ≈ 0.003 rad/s and |accel| 9.741 m/s² (so SDK 2.58.1 handles the gyro unit
  change introduced with firmware 5.16), and **no** early-stamped IMU samples
  in this first session after the camera restarted.
- Accelerometer noise (standard deviation) was ≈ 0.03 m/s² in both today's
  before and after checks, against ≈ 0.01 on 1 October; same before and after,
  so not the firmware. Cause not established.
- Cautions: with SDK 2.58.1 do not install firmware 5.17.4.24 or newer (its
  accelerometer units would be read 100× too large). In 2.58.1,
  `rs-fw-update -r` prints "timed out!" even after a successful recovery and
  may flash a second time, so never unplug while it runs. Each downgrade uses
  one of 20 allowed per camera.
- Limits: the calibration comparison covers the intrinsics and extrinsics the
  SDK reports, not the raw tables byte for byte; no release notes specific to
  5.17.3.10 were found.

### IMU calibration plan (prepared 2 October 2026; not yet run)

Tool: `tools/rs-imu-calibration/rs-imu-calibration.py` from the v2.58.1 source
tree, run as a patched copy outside the tree (research and an independent check
on 2 October; nothing was written to the camera):

- **NumPy 2 fixes.** `.astype('f').tostring()` → `.tobytes()` (otherwise the
  tool stops with an error while saving `calibration.bin`, before it offers
  to write to the camera), and keep the per-pose measurements as a list instead of
  `np.array(measurements)` (unequal sample counts would otherwise abort after
  all six poses, before the raw data is saved).
- **Gyro bias units.** SDK 2.58.1 reads the stored gyro bias as deg/s; the tool
  stores rad/s, so only ~1/57 would be applied. Store `np.degrees(...)` of the
  bias, or remove gyro bias at run time instead.
- **Jig.** The camera snug and square inside a rigid box (the tool's README uses
  the camera's retail box with a notch for the cable), mounting-screw face on
  the box bottom; cable out through a notch with slack; a level spot (< 1°)
  within cable reach of the Jetson; spacers for the pose with the cable end
  down. Two poses stand the camera on its ends (one carries the USB plug) and
  one puts the lens face down, so a bare desk is not suitable.
- **Run.** Stop other camera users; `ssh -t jetson` (a terminal is required);
  run inside `tmux` so a Wi-Fi drop does not end it (not installed yet). Poses
  in order: mounting screw down, left, up, right (lens facing out), lens down,
  lens up; about 13 s each at 100 Hz accel, hands off.
- **Two passes.** First save the raw data and answer *N* to writing; review
  offline with our own code, applying the fit from `calibration.json`
  (corrected |a| per pose ≈ 9.81 m/s², against ≈ 9.74 raw; gravity on the
  expected axis; fitted matrix near identity). Then write with `-i accel_<name>.txt gyro_<name>.txt`
  (the end-of-run write has failed on Jetsons with "failed to set power state").
  `-i` still needs the camera connected.
- **Verify.** In a fresh process the intrinsics are no longer identity; 10 s
  stationary checks in all six poses plus two or three tilted ones;
  corrected |a| within ±0.03 m/s² of 9.81 and closer than raw; per-axis means
  too, once with the camera on its own base on the levelled spot outside the box
  (the fit absorbs a crooked seat, so neither |a| nor the box poses can show it);
  gyro mean at rest recorded per axis (≈ 0 only if the bias was stored in deg/s
  or is removed at run time); still stored after a power cycle.
  Noise and bias variances stay 0 in SDK 2.58.1 (expected). Comparing with
  motion correction off needs a small addition to `tools/realsense_check.py`.
- **Limits.** RealSense provides no way to restore a factory IMU state; untested fallbacks
  are writing a neutral table (identity scale, zero bias), which should behave
  like today's default, or switching motion correction off per process. Keep
  the raw files and `calibration.json` in `~/ugv-data/imu-calib/` to re-write
  if needed. Whether a later firmware update keeps the IMU table is unknown, so
  re-check intrinsics after any firmware change.

