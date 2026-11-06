# Hardware baseline

Compiled **29 September 2026** from earlier reports, without contacting any
device. Results from **1 October 2026** on are in the sections below. Raw outputs,
photos, purchase records and network identifiers stay outside this repo.

## Evidence and chronology

- **24 August 2026:** NVMe, power bank and charger still in transit. The P50 ran the
  simulated Python backend and received 55 WebSocket packets (not real telemetry).
- **4 September 2026 bench evidence:** terminal output records NVMe boot, package
  and service checks and CUDA execution (inspected 29 September).
- **Commissioning exchange, 4 September 2026:** only one suitable USB cable, so
  Ethernet SSH was proposed to free it for the D435i.
- **29 September 2026 owner inventory:** all equipment in the README available.

## Status

| Component | Best evidence | Still open |
| --- | --- | --- |
| Jetson Orin Nano Super 8 GB | Bench pass 4 September; baseline re-checked over SSH 1 October | Sustained load, case cooling, navigation workloads |
| Kingston NV3 1 TB (`SNV3S/1000G`) | Root filesystem and cold boot, 4 September | Endurance, performance, capture load |
| Official Jetson PSU and stock fan | Lite-On `PA-1450-26`, 19 V / 2.37 A; fan ran | Retest the current setup |
| P50 | Ubuntu 22.04 x86_64 with SDK Manager; SSH on the home network, 1 October | Packages not inventoried |
| Jetson network | Key-based SSH over Wi-Fi, no Ethernet or USB, survives a reboot; USB device-mode SSH from one P50 port (1 October) | Wi-Fi range on the moving robot |
| D435i (`999AFR` kit) | USB 3; stationary indoor RGB/depth (V4L and RSUSB) and IMU (RSUSB only), 1 October; firmware 5.15.1.55 → 5.17.3.10, 2 October | IMU calibration, balcony depth, rover mount |
| UGV01 controller and drivetrain | Protocol from source, simulated adapter, 2 October ([notes](ugv01-protocol.md)); first contact 19 October; lifted drive and stops 6 November | Firmware version, floor driving, turns, Wi-Fi loss |
| Three Molicel P28A cells | Flat-top, unprotected; inspected 6 November, no dents or damage | Charging, pack use |
| PB205 / X553 / PD-to-barrel cable | Bank from its label: UGREEN PB205, P/N 90597A (160 × 80.8 × 26.7 mm, 513 g); display and button on a long side, button ends ~40 mm from the port end (13 October). Cable recorded as Adafruit 5451 (fixed 15 V, falls back to 9 V or lower; the 20 V version is 5452; confirm from the label) | Negotiated voltage under load (~25 W peak + ~2 W camera), idle shut-off, plug fit (Jetson jack 5.5×2.5 mm), polarity, runtime |
| Jetson enclosure | Waveshare 25334 (JETSON-ORIN-CASE-A), both IPEX4-to-SMA antennas on the Wi-Fi card (Main, Aux); boots, SSH works (12 October). Two threaded holes on the bottom centre line, ~65 mm apart (tape measure) | Thermals in the case; bundled CSI bracket reported not to fit the D435i |
| MacBook Pro M4 / 48 GB | Owner's inventory | ML runtime not benchmarked |

**Onboard mounting (designed 12 October, parts ordered 13 October, assembled
19 October):** see `hardware/jetson-bank-mount/README.md`. Printed tray and lid on the
two 1020 rails (170 mm centres). The case screws stay loose, because the bottom
holes have no stop and a long screw can reach the board.

The mini tripod suits stationary checks, not a rover mount. No GNSS, lidar,
working wheel odometry or localization system is established.

## Previously reported Jetson configuration

**4 September observations**, not an instruction to reinstall:

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

The umbrella `nvidia-jetpack` package was absent; a simulated install proposed 16
metapackages. cuDNN, TensorRT, VPI and OpenCV are not functionally validated. Five
idle samples read 48.5–50.3 °C and 4.49–4.53 W. DisplayPort-to-HDMI gave no signal
before flashing and was not retested; cause unknown, so we run headless.
[NVIDIA's guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/quick_start.html)
documents the JetPack 7.2.1 / L4T r39.2.1 pairing (checked 29 September 2026).

## Reproducible inspection notes

Redact names, addresses, MACs, serials and network profiles before adding a result.

### Recheck the Jetson baseline

Re-run on 1 October (result under the checkpoint):

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

These do not rerun the CUDA kernel: the smoke binary was temporary. A future GPU
check should keep its source and output.

### Checkpoint: USB-independent SSH, then D435i enumeration

Planned procedure; the result below records the route actually taken. Official
supply, stock cooling, robot stationary.

On the P50, then on the Jetson over USB SSH:

```bash
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
ip -4 route
ip -4 -br address
```

Open a second SSH session over the new link, and unplug USB only once it works.
Then put the D435i on its tripod, with the supplied cable direct to a Jetson USB-A
port (no hub), and on the Jetson:

```bash
lsusb -d 8086:0b3a
lsusb -t
```

**Pass:** fresh SSH with USB networking off, and the D435i at `8086:0b3a` with its
own USB-tree device at `5000M`. `480M` means a USB 2 fallback.

**Result, 1 October 2026: passed, by a different route.** The P50 USB link failed
on 30 September and worked again on another P50 port. The Jetson went on the home
router (Ethernet, then Wi-Fi) instead of a direct P50 cable.

- Baseline over SSH unchanged from 4 September, before that day's package changes; no
  failed units; idle 45 °C; power mode 25 W.
- With Ethernet and USB networking off, fresh SSH over Wi-Fi works and survives a
  clean reboot (back in ~45 s). Wi-Fi power saving disabled: 20 pings from the Mac
  averaged 92 ms via Jetson Wi-Fi against 21 ms via Ethernet, and 20 ms via Wi-Fi
  afterwards.
- D435i: `lsusb` shows `8086:0b3a` as Bus 2 Device 3, and `lsusb -t` shows it at
  `5000M`. Stock `uvcvideo` binds it and reports unknown depth formats; the IMU
  appears as generic HID.

Limits: Wi-Fi measured at short range in one room; temperatures and pings are spot
readings.

### Streaming setup follows enumeration

Pin the librealsense version and backend
([Jetson guide](https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md)).
Do not apply an old kernel patch or firmware upgrade by assumption. Record profiles,
versions, calibration, depth scale, frame rate, gaps, invalid depth and any drops, and
keep a replayable sample outside Git with a sanitized manifest. Repeat in balcony light
before choosing the perception task.

**Result, 1 October 2026: packaged SDK (V4L backend), RGB and depth only.**

- librealsense **2.58.1**, the latest non-beta (2.58.2–2.58.4 are betas). Its notes
  list JetPack 5.0.2, 6.0–6.2 and 7.0, not our 7.2.1. Installed from the RealSense
  apt repository (`noble`, arm64), held at `2.58.1-0~realsense.8236`, plus
  `pyrealsense2==2.58.1.10581` from PyPI. Both use the **kernel V4L backend**
  (`/dev/video*`).
- Camera firmware **5.15.1.55**; the notes list ≥ 5.17.3.10 for the D435i.
- Check with an earlier, superseded `tools/realsense_check.py`: stationary indoor
  scene, 848×480 @ 30 fps depth (Z16) + RGB8, 10 s. Depth 284 and colour 287 frames,
  29.98 fps each, no frame-number gaps, intervals 33.4 ms median / 33.7 ms max;
  receive time minus timestamp ≈ 36 ms median (colour max 134 ms, at start-up);
  global time domain; depth scale 1 mm; invalid depth 18.7 % median (43 % max);
  depth-to-colour offset 15 mm. The recording (ROS 2 `.db3`, ~590 MB per 10 s) holds
  292 depth frames against 284 delivered: frames 0–6, a counter restart at 1 about
  0.40 s in, then 285 more.
- **No IMU with V4L:** the Jetson kernel lacks HID sensor support
  (`CONFIG_HID_SENSOR_HUB` not set).

**Result, 1 October 2026: source build with RSUSB, RGB, depth and IMU.**

Source tag `v2.58.1` (commit `bf2778061d5d`), configured with
`-DCMAKE_BUILD_TYPE=Release -DFORCE_RSUSB_BACKEND=ON -DBUILD_PYTHON_BINDINGS=ON
-DPYTHON_EXECUTABLE=<venv>/bin/python -DBUILD_WITH_CUDA=OFF -DBUILD_WITH_DDS=OFF
-DBUILD_EXAMPLES=OFF -DBUILD_GRAPHICAL_EXAMPLES=OFF -DBUILD_TOOLS=ON
-DBUILD_UNIT_TESTS=OFF` (configure downloads pybind11), with `CMAKE_INSTALL_PREFIX`,
`CMAKE_INSTALL_RPATH` (`<prefix>/lib`) and `PYTHON_INSTALL_DIR` inside the prefix
`~/ugv-nav/opt/librealsense-2.58.1-rsusb`. Binaries find their library through
`RUNPATH`; an `LD_LIBRARY_PATH` would override it. ~12 min at `-j4`, temperature not
monitored. The Python link failed once, cause unknown, and passed on a `-j1` rebuild
(spot readings ≤ 48 °C during the link steps).

Tool environment: `/usr/bin/python3 -m venv ~/ugv-nav/.venv` (Python 3.12.3) with
`numpy` 2.5.3, and a `.pth` file pointing at `<prefix>/lib/python3.12/site-packages`
(PyPI wheel removed). RSUSB needs the RealSense udev rules (`librealsense2-udev-rules`
on 1 October; the source tree's `config/99-realsense-libusb.rules` since 2 October).
They reach a connected camera only after `sudo udevadm control --reload-rules &&
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=8086 && sudo
udevadm settle`.

Three 10 s trials with `--record`, 20:24–20:25 UTC, same scene, with an earlier,
uncommitted tool (sha256 `a42d1faf1eeb…`; later revisions changed only reporting,
overwrite protection, the mean-rate calculation and a filter for future-stamped
samples). The process opens only `/dev/bus/usb/*`.
Default profiles: depth and colour 848×480@30, gyro 200 Hz, accel 100 Hz.

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

- **Depth start-up:** the camera restarts its frame counter at 0 about 0.18–0.19 s
  after the first frame. The pipeline passes on only the last pre-restart frame; the
  other 4–5, and the final frame, are only in the recording.
- **IMU start-up:** samples stamped about 5 s to 1 min before the session arrive
  first, and their frame numbers continue into the session's. They appeared in every
  RSUSB run except the first, which had no earlier IMU session; origin unconfirmed.
  Separately, 6–9 gyro and 1–2 accel samples are missing around 0.06–0.14 s, in the
  recordings too.
- **Receive − timestamp** includes clock-mapping error of at least 13–20 ms, so it
  is not a clean latency measure.
- **IMU at rest:** |accel| = 9.743–9.745 m/s² (≈ 0.7 % below 9.81); gyro mean
  ≈ 0.002 rad/s. The camera reports default IMU intrinsics (identity scale, zero
  bias and variances), so apparently no stored calibration.
- Seven earlier RSUSB runs that day showed the same patterns; this table supersedes
  their counts.

So: identify frames by (number, timestamp), drop samples stamped before a session
starts, and ignore the first ~0.5 s of each stream, counted from its first non-stale
sample (≈ 1 s after pipeline start).

**System changes on the Jetson, 1 October 2026:** hostname set; Wi-Fi profile added
(autoconnect, power saving off); RealSense apt repository and key added
(`/etc/apt/sources.list.d/librealsense.list`, `/etc/apt/keyrings/librealsenseai.gpg`);
`librealsense2`, `-gl`, `-utils` and `-udev-rules` 2.58.1 held, with 45 automatic
packages (GTK/X11/Mesa, `v4l-utils`, `at`). Build dependencies: `libusb-1.0-0-dev`,
`libssl-dev`, `pkg-config` (`git`, `python3.12-dev` already present). Upgraded as
dependencies: Mesa, GLib, bzip2, Python 3.12 (`3.12.3-1ubuntu0.17`), OpenSSL; no L4T,
CUDA or kernel package changed. Source tree `~/src/librealsense-2.58.1`; 11 recordings
(6.1 GB) in `~/ugv-data/recordings`.

**Cleanup, 2 October 2026: packaged SDK removed.** Installed
`config/99-realsense-libusb.rules` as `/etc/udev/rules.d/99-realsense-libusb.rules`
(covers the D435i and its firmware-recovery IDs), purged the 4 packages with
`--autoremove` (48 in all: 44 of the 45 automatic ones; `gir1.2-glib-2.0-dev` stays),
and removed the apt repository and key. `dpkg --audit` clean; all three sensors show.

Two 4 s checks afterwards: gyro 200.4–200.5 Hz, accel 100.6 Hz, 9 gyro and 3 accel
samples stamped before the start and **no** missing IMU samples, unlike every 1 October
run; cause unknown. One earlier 4 s run reported no mean IMU rate and kept 3 accel and
11 gyro samples more than the next two. Not reproduced; the tool now drops timestamps
more than 1 s ahead of arrival (`future_stamped`).

**Firmware update, 2 October 2026: 5.15.1.55 → 5.17.3.10.**

- Image `D4XX_FW_Image-5.17.3.10.bin` from RealSense's SDK firmware mirror: 1,573,660
  bytes, SHA-256 `4c347e3a…e4d2`. Rollback image `D4XX_FW_Image-5.15.1.0.bin`
  (listed as equal to 5.15.1.55): SHA-256 `29bd3181…7028`. Both are under the
  RealSense licence, kept in `~/ugv-data/firmware/`, not in Git.
- Before: device report, calibration dump (`rs-enumerate-devices -c`) and a 5 s check
  saved. Backup with `rs-fw-update -b`: 2,097,152 bytes (archive only; a locked camera
  cannot be flashed back from it).
- Flash: `rs-fw-update -f <image>`, detached from SSH, 08:12:20–08:12:53 UTC. It
  printed "successfully updated to FW: 5.17.3.10", then crashed on exit (code 139,
  segmentation fault). The camera had already reconnected normally.
- After 90 s: `rs-fw-update -l` shows 5.17.3.10, USB 3.2 and all three sensors. The
  calibration dump is identical apart from the USB device number. A 10 s check shows
  identical intrinsics and extrinsics, unchanged rates (gyro 200.4 Hz, accel 100.6 Hz,
  depth 29.6 fps, colour 30.0 fps), no missing frames, gyro at rest ≈ 0.003 rad/s and
  |accel| 9.741 m/s² (so SDK 2.58.1 handles the gyro unit change from firmware 5.16),
  and **no** early-stamped IMU samples in this first session after the camera restarted.
- Accelerometer noise was ≈ 0.03 m/s² before and after, against ≈ 0.01 on 1 October,
  so not the firmware. Cause unknown.
- Cautions: with SDK 2.58.1 do not install firmware 5.17.4.24 or newer (accelerometer
  units would read 100× too large). `rs-fw-update -r` prints "timed out!" even after
  success and may flash twice, so never unplug while it runs. Each downgrade uses one
  of 20 allowed per camera.
- Limits: the comparison covers reported intrinsics and extrinsics, not the raw
  tables. No release notes for 5.17.3.10 were found.

**Soak test, 2 October 2026: 20 minutes of streaming with CPU alignment.**
`tools/jetson_soak.py --minutes 20` (13:34–13:54 UTC; Jetson bare on the desk, stock
fan, 25 W mode, official supply): depth + colour 848×480@30, gyro 200 Hz, accel
100 Hz, every depth frame aligned to colour on the CPU (`rs.align`, no CUDA), no
recording. First 10 s interval excluded:

| Measure | Result |
| --- | --- |
| Frames | depth/colour 35,674 each (29.98 fps), gyro 238,100 (200.1 Hz), accel 119,167 (100.1 Hz) |
| Frame-number gaps / counter resets | 0 / 0 on all streams |
| Longest interval | depth/colour 33.4 ms, gyro 5.0 ms, accel 10.0 ms |
| Frame sets not processed in time (queue drops) | 0; processing held 30 per second (28.8 in the first interval) |
| Alignment time per frame set, p95 | 22.3–22.9 ms per interval |
| Junction temperature (`tj`) | 48.2 °C at start → 50.0 °C max, flat after ~15 min |
| Board input power (`VDD_IN`, tegrastats) | 5.2 W median, 5.25 W max |
| CPU load / GPU load / RAM | ~15 % average (max 20 %) / 0 % / 1.2 GB |
| Clocks (lowest seen) | CPU 730 MHz, GPU 306 MHz (load-driven scaling) |

Start-up IMU samples set aside: 11. Limits: light load, no enclosure, room
temperature not measured. A heavier soak is needed before claiming sustained compute.

### IMU calibration plan (prepared 2 October 2026; deferred 9 October)

**Deferred on 9 October 2026.** The camera applies the neutral table (identity scale,
zero offsets; raw |g| 9.74 m/s² against 9.81, ~0.7 % scale error; real offsets unknown),
which costs little at 0.1 m/s. Interim: record the at-rest gyro offset and per-axis gravity with
`tools/realsense_check.py`, subtract the offset at start-up, and note the calibration
state in every manifest.

When we do calibrate: use the retail box's foam tray, cable through the lid seam
(~1.5° tilt, within the tool's ~5° limit) or a notch. A pose counts when the
accelerometer is within 0.87 m/s² of the target for 3 s. Tool:
`tools/rs-imu-calibration/rs-imu-calibration.py` from the v2.58.1 tree, as a patched
copy. Nothing has been written to the camera.

- **NumPy 2 fixes.** `.astype('f').tostring()` → `.tobytes()`, or saving
  `calibration.bin` fails. Keep per-pose measurements as a list, not
  `np.array(measurements)`, or unequal counts abort after all six poses.
- **Gyro bias units.** SDK 2.58.1 reads stored bias as deg/s; the tool stores rad/s,
  so only ~1/57 applies. Store `np.degrees(...)` of the bias, or remove it at run time.
- **Jig.** Camera snug in a rigid box on a level spot (< 1°), mounting-screw face down,
  with spacers for the cable-end-down pose.
- **Run.** `ssh -t jetson`, inside `tmux` (not installed yet). Poses in order: mounting
  screw down, left, up, right (lens out), lens down, lens up; about 13 s each at 100 Hz
  accel, hands off.
- **Two passes.** Save raw data and answer *N* to writing. Review `calibration.json`
  offline (corrected |a| per pose ≈ 9.81 m/s² against ≈ 9.74 raw). Then write with
  `-i accel_<name>.txt gyro_<name>.txt`, camera connected (the end-of-run write has
  failed on Jetsons with "failed to set power state").
- **Verify.** Intrinsics no longer identity in a fresh process. 10 s checks in all six
  poses plus two or three tilted: corrected |a| within ±0.03 m/s² of 9.81; per-axis
  means once outside the box; gyro mean per axis; still stored after a power cycle.
  Noise and bias variances stay 0 in SDK 2.58.1 (expected).
- **Limits.** RealSense cannot restore a factory IMU state. Untested fallbacks: write a
  neutral table, or switch motion correction off per process. Keep raw files in
  `~/ugv-data/imu-calib/`. Re-check intrinsics after any firmware change.

## UGV01 first contact (19 October 2026)

Read-only, over Wi-Fi (the printed mount covers the Jetson's 40-pin header). Tracks
lifted. Board OLED at power-on: `AP: UGV`, `ST: OFF`, `V: 11.11`. The Mac joined the
board's access point and used `GET http://192.168.4.1/js?json=<command>`, which runs
the command and returns the reply in the HTTP body.

| Request | Reply | Reading |
| --- | --- | --- |
| `{"T":1,"L":0,"R":0}` (stop) | sent | — |
| `{"T":130}` | `T:1001` L 0, R 0, r −1.06°, p 0.39°, y `"null"`, v 11.82 V | Link works; robot level; ~3.94 V/cell. Yaw is not filled in. |
| `{"T":126}` | `T:1002` r −1.03, p 0.45, y −179.45; ax −7.4, ay −18.1, az 982.2; gx 0.12, gy 0.10, gz 4.00; mx 12, my 0, mz 0; temp 0 | Gravity on z (≈981, units look like cm/s²). Magnetometer looks inactive. No temperature. |

No `temp` key in `T:1001` suggests `ugv_base_general` ≤ 0.90. OLED (11.11 V) and polled
(11.82 V) voltage differ; cause not checked.

**Home network (same day):** `T:407` (mode 3 = access point + station, non-default AP
password) joined the board to the 2.4 GHz network; the address is in `CLAUDE.local.md`.
`T:407` restarts the board's Wi-Fi and blocks up to 15 s, so no HTTP reply arrives. A
first attempt sent the AP password under a wrong key, which leaves the access point
without a password; check the `T:405` reply afterwards. From the Mac on the home
network, `T:130` returned `T:1001` (11.59 V); five round trips took 19, 27, 18, 19 and
50 ms (median 19 ms). The adapter gained `HttpTransport`, and the probe `--http <host>`.

**Probe from the Jetson (19 October 2026, 13:32 local).** Repo rsynced (git `262122c`
plus uncommitted docs); `pyserial 3.5` added to `~/ugv-nav/.venv` (Python 3.12.3).
Both on home Wi-Fi, robot level and still:

    PYTHONPATH=src .venv/bin/python tools/ugv01_probe.py --http <board address>

| Measure | Value |
| --- | --- |
| Requests / failed / overflowed replies | 14 / **0** / 0 |
| Valid `T:1001` / invalid / unsolicited | 10 / 0 / 0 (exit status 0) |
| Round trip, probe-reported | last 16 ms, max 101 ms |
| Round trip, from print timestamps (gap − 0.2 s spacing) | 11–101 ms, median ≈ 18 ms; the two slowest are the first two requests, two more at ~60 ms |
| Battery `v` | 11.52 V (tilt check minutes earlier: 11.54 V; earlier today 11.82 V, 11.59 V) |
| `T:139` speed rate | L 1, R 1 |
| `T:1001` roll / pitch | −1.48 to −1.67° / −0.01 to −0.21° |
| `T:1001` keys | `T L R r p v y`; `y` is the string `"null"` |

**Tilt check (same session, from the Mac, robot level).** Right after `T:407` the owner
saw a level robot report r −20.4°, p −25.9°; before it, r −1.1°, p 0.4°. Now:
5 × (`T:130`, 1 s, `T:126`, 1 s). Accelerometer angles from `T:1002`:
roll = atan2(ay, az), pitch = atan2(−ax, √(ay² + az²)).

| # | `T:1001` r | `T:1001` p | `T:1002` r | `T:1002` p | accel roll | accel pitch | \|a\| |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | −1.63 | −0.13 | −1.53 | −0.04 | −1.56 | 0.06 | 987.9 |
| 2 | −1.53 | −0.07 | −1.49 | −0.11 | −1.47 | −0.11 | 988.8 |
| 3 | −1.50 | −0.09 | −1.52 | −0.10 | −1.48 | −0.05 | 986.4 |
| 4 | −1.53 | −0.04 | −1.53 | −0.16 | −1.53 | 0.00 | 986.9 |
| 5 | −1.53 | −0.24 | −1.57 | −0.09 | −1.50 | 0.00 | 988.4 |

Board and accelerometer agree within **0.24°** (limit 2°), so the −20°/−26° reading was
transient. Treat `r`/`p` as unreliable for some seconds after a blocking command; how
long is not measured. Round trips 21–170 ms (first request slowest).

**Gyro z at rest is noise, not a fixed offset.** Seven single readings: 4.00, −0.44,
1.69, −1.81, 0.50, −0.56, −1.12 (gx, gy similar, up to −2.3). Average over a few
seconds at start-up.

## First guarded drive (6 November 2026)

First motor movement. Tracks lifted, robot on a stand on the floor, owner at the
power switch, cells inspected first. Both tracks forward at 0.05 m/s for 1.0 s, run
from the Jetson over Wi-Fi. Battery 12.14 V before, 12.13 V after. Git `aceaf9f`, then
`50a4ffd` for the step c retry:

    PYTHONPATH=src .venv/bin/python tools/ugv01_drive_check.py --http <board address>
    PYTHONPATH=src .venv/bin/python tools/ugv01_drive_check.py --http <board address> --steps c

Data, not in git: `recordings/ugv01_drive_check_20261106T172941Z.csv` and
`recordings/ugv01_drive_check_20261106T175055Z.csv`.

| Step | What stopped the tracks | Timer starts at | First reading below 0.005 m/s | Tool printed |
| --- | --- | --- | --- | --- |
| a | host stop | first STOP written | **0.26 s** | 1.33 s |
| b | command lease, 0.55 s after the last accepted command | client's STOP | **0.26 s** | 0.26 s |
| c | firmware heartbeat | last `T:1` written | **3.26 s** | 3.26 s |

One trial each. The tool waits for the last run of still readings. In step a, R read
above zero twice more, at +0.31 s and +1.29 s, and the second one gave 1.33 s. The
owner saw no twitch, so that is not a real stop time.

The first try of step c aborted: a request timed out 0.2 s into the drive and the
guard disarmed. The host's STOP reached the board about 0.5 s after the last good
`T:1`, and the tracks read 0 another 0.27 s later.

- The heartbeat works. During the silence the host sent 47 `T:130` and no `T:1`, and
  the tracks stopped by themselves. So `T:130` does not refresh it.
- Speed control looks right: readings average about 0.05 m/s, and the owner saw both
  tracks run forward.
- Feedback moves in steps of about 0.025 m/s when no `T:1` is being sent.
- 68 of 8,760 HTTP requests failed (0.78 %), in irregular bursts. Feedback gaps reached
  0.72 s, and 15 were over the client's 0.5 s link timeout. Any failed request during a
  drive stops it. Guess: the board's 2.4 GHz link is the weak point.
- Board pitch reads about +10°, but the owner says the robot is not tilted. Cause
  unknown.

Still unknown: the floor, stop distance, the 0.10 m/s cap, left/right mapping (no turn
sent yet), a real Wi-Fi loss, repeatability.
