# Hardware baseline

Status and measured results for each device, oldest first. Dated history:
`docs/log.md`.

## Status

| Component | Best evidence | Still open |
| --- | --- | --- |
| Jetson Orin Nano Super 8 GB | Bench pass 4 September; baseline re-checked over SSH 1 October | Sustained load, navigation workloads |
| Kingston NV3 1 TB (`SNV3S/1000G`) | Root filesystem and cold boot, 4 September | Endurance, performance, capture load |
| Official Jetson PSU and stock fan | Lite-On `PA-1450-26`, 19 V / 2.37 A; fan ran (4 September); powered the 20-minute soak (2 October) | — |
| Jetson network | Key-based SSH over Wi-Fi, no Ethernet or USB, survives a reboot (1 October) | Wi-Fi range on the moving robot |
| D435i | USB 3; stationary indoor RGB/depth (V4L and RSUSB) and IMU (RSUSB only), 1 October; firmware 5.15.1.55 → 5.17.3.10, 2 October | IMU calibration, balcony depth, mount on the robot (so far only a mini tripod; the case's bundled CSI bracket is reported not to fit) |
| UGV01 controller and drivetrain | Protocol from source, simulated adapter, 2 October ([notes](ugv01-protocol.md)); first contact 19 October; floor drive and stops 6 November | Firmware version, stop distance, the 0.10 m/s cap, turns, a real Wi-Fi loss, repeatability |
| Three Molicel P28A cells | Flat-top, unprotected, as Waveshare asks (the board protects them); inspected 6 November, no dents or damage; powered the 6 November drive | Charging |
| PB205 / X553 / PD-to-barrel cable | Bank from its label: UGREEN PB205, P/N 90597A, 513 g. Cable recorded as Adafruit 5451 (fixed 15 V, falls back to 9 V or lower; the 20 V version is 5452; confirm from the label) | Negotiated voltage under load (~25 W peak + ~2 W camera), idle shut-off, plug fit (Jetson jack 5.5×2.5 mm), polarity, runtime |
| Jetson enclosure | Waveshare 25334 (JETSON-ORIN-CASE-A), both IPEX4-to-SMA antennas on the Wi-Fi card (socket 1 Main, 2 Aux); boots, SSH works (12 October) | Thermals in the case |
| Printed mount | Assembled 19 October ([design and as built](../hardware/jetson-bank-mount/README.md)) | Case screws only hand-snug |

## Jetson configuration (4 September 2026)

| Item | Value |
| --- | --- |
| Flash host/tool | P50, Ubuntu 22.04 x86_64; SDK Manager `2.4.1-13536` |
| Installed release | JetPack `7.2.1`; Jetson Linux `R39.2.1`, a pairing [NVIDIA's guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/quick_start.html) documents (checked 29 September) |
| OS / kernel | Ubuntu `24.04.4` aarch64 / `6.8.12-1021-tegra` |
| BSP package | `nvidia-l4t-core 39.2.1-20260806224157` |
| Root filesystem | `/dev/nvme0n1p1`, ext4, before and after normal cold boot |
| CUDA compiler | CUDA `13.2`, `nvcc V13.2.86` |
| CUDA execution | `CUDA kernel smoke: PASS \| Orin \| CC 8.7 \| value=42` (binary not kept, so not rerun on 1 October) |
| Package/services | Empty `dpkg --audit`; successful `apt-get -s check`; no failed systemd units |
| Idle (five samples) | 48.5–50.3 °C, 4.49–4.53 W |

The umbrella `nvidia-jetpack` package was absent; a simulated install proposed 16
metapackages. cuDNN, TensorRT, VPI and OpenCV are not functionally validated.
DisplayPort-to-HDMI gave no picture before flashing and was not retested; cause
unknown, so we run headless.

## Jetson and camera (1–2 October 2026)

### Checkpoint: USB-independent SSH, then D435i enumeration

**Result, 1 October 2026: passed.** Official supply, stock cooling, robot
stationary. The Jetson went on the home router (Ethernet, then Wi-Fi) instead of a
direct cable to the P50.

- Baseline over SSH unchanged from 4 September (checked before that day's package
  changes); no failed units; NVMe root 4 % used; idle 45 °C; power mode 25 W.
- With Ethernet and USB networking off, fresh SSH over Wi-Fi works and survives a
  clean reboot (`sudo systemctl reboot`; back in ~45 s, 22 ms average ping). The
  5 GHz link: −28 dBm, 866 Mbit/s. 20 pings from the Mac with Wi-Fi power saving
  on: 92 ms via Wi-Fi, 21 ms via Ethernet; with it off: 20 ms via Wi-Fi, 30 ms via
  Ethernet. Power saving is now off.
- D435i, supplied cable direct to a Jetson USB-A port (no hub): `lsusb -d 8086:0b3a`
  finds it (USB 3.2 descriptor, `bcdDevice 50.f1`) and `lsusb -t` shows it at
  `5000M` (`480M` would mean a USB 2 fallback). Stock `uvcvideo` binds
  `/dev/video0–5` and logs "Unknown video format" for depth; the IMU appears as
  generic HID.

Limits: Wi-Fi measured at short range in one room; temperatures and pings are spot
readings.

### Streaming setup follows enumeration

**Result, 1 October 2026: packaged SDK (V4L backend), RGB and depth only.**

- librealsense **2.58.1**, the latest non-beta (2.58.2–2.58.4 are betas). Its notes
  list JetPack 5.0.2, 6.0–6.2 and 7.0, not our 7.2.1
  ([Jetson guide](https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md)).
  Installed from the RealSense apt repository (`noble`, arm64), held at
  `2.58.1-0~realsense.8236`, plus `pyrealsense2==2.58.1.10581` from PyPI. Both use
  the **kernel V4L backend** (`/dev/video*`). Removed on 2 October.
- Camera firmware **5.15.1.55**; the notes list ≥ 5.17.3.10 for the D435i (updated
  on 2 October, below).
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

**Result, 1 October 2026: source build with RSUSB, RGB, depth and IMU.** Build and
environment: `docs/log.md`, 1 October.

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
  bias and variances).
- Seven earlier RSUSB runs that day showed the same patterns; this table supersedes
  their counts.

So: identify frames by (number, timestamp), drop samples stamped before a session
starts, and ignore the first ~0.5 s of each stream, counted from its first non-stale
sample (≈ 1 s after pipeline start).

**2 October 2026, after removing the packaged SDK:** two 4 s checks showed gyro
200.4–200.5 Hz, accel 100.6 Hz, 9 gyro and 3 accel samples stamped before the start
and **no** missing IMU samples, unlike every 1 October run; cause unknown. One
earlier 4 s run reported no mean IMU rate and kept 3 accel and 11 gyro samples more
than the next two. Not reproduced; the tool now drops timestamps more than 1 s ahead
of arrival (`future_stamped`).

**Firmware update, 2 October 2026: 5.15.1.55 → 5.17.3.10** (steps: `docs/log.md`).

- Image `D4XX_FW_Image-5.17.3.10.bin` from RealSense's SDK firmware mirror: 1,573,660
  bytes, SHA-256 `4c347e3a…e4d2`. Rollback image `D4XX_FW_Image-5.15.1.0.bin`
  (listed as equal to 5.15.1.55): SHA-256 `29bd3181…7028`. Both are under the
  RealSense licence, kept in `~/ugv-data/firmware/`, not in Git. The backup
  (`rs-fw-update -b`, 2,097,152 bytes) is an archive only: a locked camera cannot be
  flashed back from it.
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

### Soak test (2 October 2026)

20 minutes of streaming with CPU alignment. `tools/jetson_soak.py --minutes 20` (13:34–13:54 UTC; Jetson bare on the desk, stock
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
temperature not measured.

### IMU calibration (deferred 9 October 2026)

The camera applies the neutral table (identity scale, zero offsets): raw |g| reads
9.74 m/s² against 9.81, a ~0.7 % scale error, which costs little at 0.1 m/s; the
real offsets are unknown. For now: record the at-rest gyro offset and per-axis
gravity with `tools/realsense_check.py`, subtract the offset at start-up, and note
the calibration state in every manifest. Nothing has been written to the camera.

Found while preparing it (2 October): the v2.58.1 tree's
`tools/rs-imu-calibration/rs-imu-calibration.py` needs NumPy 2 fixes
(`.astype('f').tostring()` → `.tobytes()`; keep per-pose measurements as a list),
and SDK 2.58.1 reads stored gyro bias as deg/s while the tool stores rad/s, so store
`np.degrees(...)` of the bias. RealSense cannot restore a factory IMU state. Full
procedure: `git show 4107b98:docs/hardware.md`, section "IMU calibration plan".

## UGV01 first contact (19 October 2026)

Read-only, over Wi-Fi, robot on the floor. Board OLED at power-on: `AP: UGV`, `ST: OFF`,
`V: 11.11`. The Mac joined the board's access point and used
`GET http://192.168.4.1/js?json=<command>`. After a stop (`{"T":1,"L":0,"R":0}`):

| Request | Reply | Reading |
| --- | --- | --- |
| `{"T":130}` | `T:1001` L 0, R 0, r −1.06°, p 0.39°, y `"null"`, v 11.82 V | Link works; robot level; ~3.94 V/cell. The OLED showed 11.11 V; cause of the gap not checked. |
| `{"T":126}` | `T:1002` r −1.03, p 0.45, y −179.45; ax −7.4, ay −18.1, az 982.2; gx 0.12, gy 0.10, gz 4.00; mx 12, my 0, mz 0; temp 0 | Gravity on z (the source gives mg). No temperature. |

**Home network (same day).** After `T:407` (mode 3 = access point + station,
non-default AP password) the board joined the home 2.4 GHz network. From the Mac
there, `T:130` returned `T:1001` (11.59 V); five round trips took 19, 27, 18, 19 and
50 ms (median 19 ms).

**Probe from the Jetson (19 October 2026, 13:32 local).** Repo rsynced (git `262122c`
plus uncommitted docs); `pyserial 3.5` added to `~/ugv-nav/.venv`. Both on home
Wi-Fi, robot level and still:

    PYTHONPATH=src .venv/bin/python tools/ugv01_probe.py --http <board address>

| Measure | Value |
| --- | --- |
| Requests / failed / overflowed replies | 14 / **0** / 0 |
| Valid `T:1001` / invalid / unsolicited | 10 / 0 / 0 (exit status 0) |
| Round trip, probe-reported | last 16 ms, max 101 ms |
| Round trip, from print timestamps (gap − 0.2 s spacing) | 11–101 ms, median ≈ 18 ms; the two slowest are the first two requests, two more at ~60 ms |
| Battery `v` | 11.52 V (tilt check minutes earlier: 11.54 V) |
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
1.69, −1.81, 0.50, −0.56, −1.12 (gx, gy similar, up to −2.3).

## First guarded drive (6 November 2026)

First motor movement. Robot on the floor with clear space ahead, owner at the
power switch, cells inspected first. (Recorded on 6 November as "tracks lifted";
corrected 10 November: the tracks were on the floor, so these stops were under
real load.) Both tracks forward at 0.05 m/s for 1.0 s, run
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

One trial each. In step a, R read above zero twice more (+0.31 s, +1.29 s); the tool
times the last run of still readings, so it printed 1.33 s. The owner saw no twitch,
so that is not a real stop time.

The first try of step c aborted: a request timed out 0.2 s into the drive and the
guard disarmed. The host's STOP reached the board about 0.5 s after the last good
`T:1`, and the tracks read 0 another 0.27 s later.

- The heartbeat works. During the silence the host sent 47 `T:130` and no `T:1`, and
  the tracks stopped by themselves. So `T:130` does not refresh it.
- At a 0.05 m/s command the readings average about 0.05 m/s, and the owner saw both
  tracks run forward.
- 68 of 8,760 HTTP requests failed (0.78 %), in irregular bursts. Feedback gaps reached
  0.72 s, and 15 were over the client's 0.5 s link timeout. Any failed request during a
  drive stops it.
- Board pitch reads about +10°, but the owner says the robot is not tilted. Cause
  unknown.
