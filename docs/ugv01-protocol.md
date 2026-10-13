# UGV01 controller protocol (host adapter reference)

Written **2 October 2026** from firmware source, vendor binaries and vendor
documentation. **Nothing on this page has been observed on our robot**: no
serial port was opened and the board was not powered for this work. Every
runtime behaviour below comes from source or documentation and must be
measured in a scoped commissioning task (tracks off the ground) before we rely
on it. The adapter lives in `src/ugv_nav/ugv01/`.

## Firmware identity

| Item | Finding |
| --- | --- |
| Source | [waveshareteam/ugv_base_general](https://github.com/waveshareteam/ugv_base_general), sketch `General_Driver/`, ESP32-WROOM-32 on the Waveshare General Driver for Robots board |
| Revision read | `d308df91b333a513f45a238bef9ba9a0a5edf64c` (2025-11-28, OLED `version: 0.95`). The protocol files (`uart_ctrl.h`, `movtion_module.h`, `json_cmd.h`, `ugv_config.h`) are unchanged since `f8fc989` (2024-03-24, `version: 0.90`) |
| Licence | GPL-3.0. Waveshare host apps: `ugv_rpi` GPL-3.0, `ugv_jetson` AGPL-3.0. Only protocol facts were taken; **no firmware or host code is copied here**, so the clean host-side reimplementation carries no GPL/AGPL obligations |
| Factory image | `UGV01_FACTORY.zip` (sha256 `4aed26aa7001d80ba53ecec182800f92e39398af182b478ba0d769b2fd67d3cd`), app image `bin/UGV01_V0.9.ino.bin` (sha256 `493084393c32c6177971d4726b94e8d9fb159d1efbe03bf9f40d9d2185655113`) is the same firmware family (`version: 0.90`, same strings and web UI) |
| Robot model setting | Source: `mainType` 3 = UGV01, the only closed-loop (PID, m/s) path. A data-byte comparison against the repo build suggests the factory image is compiled with 3 (inference). GitHub HEAD compiles 1 (open loop), so a reflash from HEAD would silently change the speed unit |
| Caveat | The UGV01 wiki also links `UGV01_BASE.zip`, an older, incompatible firmware (1,000,000 baud, `{"T":0}` stop, heartbeat refreshed by any JSON). **Which firmware this board runs is unverified.** OLED clues at power-on: line 1 `version: 0.9x`, line 0 `UGV` (not `WAVE ROVER`) |

## Link and framing

- **Port:** ESP32 UART0, **115200 8N1** (1,000,000 would indicate the older firmware).
  Two routes: the 40-pin header UART (Jetson device node unverified on JetPack
  7.2.1) or the board's USB-C through a CP2102 whose DTR/RTS drive the ESP32
  reset/boot pins, so opening that port may reset (reboot) the board.
  `SerialTransport.open` clears the lines after opening, RTS then DTR
  (Waveshare's order; they cannot be held off across the open). Whether opening
  the USB route still resets the board must be measured in commissioning: a ROM
  boot banner during the probe's passive listen means it did. The 40-pin UART
  has no DTR/RTS path.
- **Host to board:** one JSON object per line ending in `\n`; selector key `"T"`
  (integer). No ACK, NAK or checksum; parse errors are dropped silently.
- **Board to host:** CRLF JSON lines, interleaved with (a) an echo of every
  parsed host line, printed *before* the command runs (default on), (b)
  plain-text debug lines, (c) a Wi-Fi status object (T:405) with **no newline**
  that glues onto the next line and can contain plaintext Wi-Fi passwords.
  The parser extracts JSON objects from arbitrary text, ignores echoes (they
  carry the host's own `T`), and never raises; the probe redacts passwords,
  SSIDs, MAC and IP addresses before printing.
- Any byte received from serial start-up until the boot mission ends (several
  seconds; longer in Wi-Fi STA mode) aborts it; with debug text on,
  `[missionPlay finished.]` marks the end.

## Commands the adapter sends

| JSON | Meaning | Units and notes |
| --- | --- | --- |
| `{"T":1,"L":l,"R":r}` | Track speed setpoints (left, right) | m/s on the closed-loop path; positive = forward per wiki (polarity and side mapping unverified). Both keys must be numbers, otherwise a silent no-op. `abs(value) > 2.0` is **ignored, not clamped**, yet still refreshes the heartbeat. Open-loop types would read the value as duty/512 (0.5 = full on) |
| `{"T":1,"L":0.0,"R":0.0}` | Normal stop | Closed loop: a PID decel, not a brake (overshoot possible, unmeasured) |
| `{"T":130}` | One T:1001 reply | Does not refresh the heartbeat |
| `{"T":126}` | One T:1002 reply (probe only) | Does not refresh the heartbeat |
| `{"T":139}` | Speed-rate reply (probe only) | Firmware-side per-side multiplier, 0..1 |

Deliberately **not** sent: `T:0` (no-op in this firmware), `T:115` (not a stop
on the closed-loop path), `T:11` (unclamped PWM; disables the PID and leaves a
stale integrator), `T:13` (not needed yet), and every configuration or
persistent command (`T:2` PID gains, `T:111` blocking delay, `T:136` heartbeat
period, `T:900` robot model, `T:131/142/143/605` stream/echo/debug settings,
`T:600/604` reboot/erase, file and mission writes, Wi-Fi and ESP-NOW
configuration). Those belong to commissioning tasks.

## Feedback the adapter parses

| Reply | Fields (units) | Caveats |
| --- | --- | --- |
| T:1001 | `L`, `R` track speed (m/s); `r`, `p`, `y` (deg); `v` battery (V); `temp` ESP32 die (°C) | Per-loop speed estimate, about 0.03 m/s quantisation (computed, not measured); no timestamp, sequence number or encoder counts, so it is timestamped with host monotonic time at receipt; `v` can be 10 s stale; `temp` absent before mid-2024 builds; builds from `b113287` (May 2024, still labelled 0.90) send `"y":"null"`; earlier 0.90 builds (likely the factory image) and later builds send a numeric `y`; IMU frame and yaw calibration unknown |
| T:1002 | `ax..az` (mg), `gx..gz` (deg/s), `mx..mz` (~µT), `r`, `p`, `y` (deg) | Sensor frame, mapping to the chassis unknown |
| T:139 | `L`, `R` speed-rate multipliers (0..1) | |

`valid` is false when a speed is missing, non-numeric, non-finite or above
2.5 m/s (open-loop types can report PWM counts there).

## Safety behaviour

### Firmware (from source, unmeasured)

- **Heartbeat:** 3000 ms. Refreshed only by `T:1` (when L and R are numbers,
  before the range check), `T:11` and `T:13`, from any source (serial, HTTP,
  ESP-NOW, missions). Feedback requests do not refresh it. On expiry it calls
  setpoint 0 once (closed loop: PID decel); it does not latch, so the next
  motion command from any source resumes motion.
- **No latched emergency stop.** The physical backstop is the power switch.
- **Ways the backstop weakens:** `T:136` with a negative value disables it;
  anything that blocks the firmware loop (`T:111`, mission playback) holds the
  last duty; a stream of out-of-range `T:1` refreshes it without applying;
  an open web-UI tab resends its last `T:1` every 1.5 s; `T:2` with zero gains
  freezes the integrator. Wi-Fi (default access point with a published
  password, unauthenticated `/js` endpoint) and ESP-NOW from any sender can
  inject motion by default.
- **Start-up:** motor pins are undefined for roughly the first 1.5-4 s of boot;
  the heartbeat fires once at about 3 s uptime.

### Host adapter (this repo)

| Decision | Choice | Reason |
| --- | --- | --- |
| Speed limit | Default cap **0.10 m/s**, configurable up to 0.5 m/s | 20 % of the wiki range, and only ~20 % duty if the board turns out to be on an open-loop model |
| Out-of-cap / NaN / inf | **Reject**, never clamp; the guard disarms as for a fault | Such a value is a caller bug or unit mix-up; clamping each track separately would also change the turn ratio |
| Command lease | **0.5 s** (0.05-1.0 allowed), checked against the client's own monotonic clock at every write | A stale command moves the robot at most 5 cm at the default cap |
| Send rate | **10 Hz** motion + T:130 poll, regardless of caller tick rate | Matches the firmware PID's 100 ms sample; ~12 % of the link with echoes |
| Link health | Up while valid T:1001 is ≤ 0.5 s old | Polled, so round-trip evidence only while nothing else makes the board print T:1001 (the T:131 stream, possibly enabled by `/boot.mission`, or web/ESP-NOW T:130 requests); commissioning checks this (the probe's `unsolicited_base_feedback`). Invalid feedback or an echo alone never counts |
| Stop | Written immediately on every transition; resent for 1 s and while fresh feedback shows motion; then the host goes quiet | Matches the source's "resend until L and R read 0"; quiet lets the firmware heartbeat act as backstop |
| Re-arm | Explicit `arm()` plus a new command after expiry, stop, fault, invalid input, link loss or a backwards clock | No stale command can resume; arming needs a live link |
| Reconnect | Stop is written at once when the link returns | Stops sent during a silent outage never arrived, and the board keeps its last setpoint for up to 3 s |

Limits: the host cannot stop the robot after the host itself fails; that
depends on the firmware heartbeat (3 s plus one loop plus decel; unmeasured).
"Stationary" means a feedback reading of exactly 0, which the quantised
estimate can also report while creeping slowly. The simulator is idealised
(instant speed changes, no noise, no boot log).

## Not verified on hardware

All of it: firmware identity and version on our board, effective `mainType`
(compiled default plus any `T:900` in `/boot.mission`), baud rate, device node
and wiring, DTR/RTS reset behaviour, echo and debug defaults, T:1001 field set,
units, signs and side mapping, loop period and feedback rate, stop latency and
overshoot for `T:1 0,0`, heartbeat latency, behaviour on cable pull and host
crash, and the drivetrain constants (wheel diameter 0.0523 m, 1092 counts/rev,
track width 0.141 m).

## Open questions (for commissioning)

1. Which firmware runs on the board, and what does `{"T":602}` (boot mission
   listing) show? Do not send `T:900` until the model setting is confirmed.
2. Which physical link (40-pin UART or USB-C) and which `/dev` node; does
   opening the USB route reset the ESP32?
3. Measured stop time and distance for `T:1 0,0`, heartbeat expiry, host crash
   and cable pull, with tracks lifted; any lurch on PID resume.
4. Loop period and achievable T:1001 rate; whether the factory build uses
   ArduinoJson 6 (256-byte document limit) or 7.
5. Encoder polarity, side mapping and real track width.
6. Whether to lock down Wi-Fi/ESP-NOW (a persistent configuration change).
7. Keep the noisy per-loop speed estimate, or plan a firmware change for
   cumulative counts and timestamps?

## Sources

- ugv_base_general @ `d308df9`: `General_Driver/{General_Driver.ino, uart_ctrl.h,
  json_cmd.h, movtion_module.h, ugv_config.h, ugv_advance.h, wifi_ctrl.h,
  esp_now_ctrl.h, http_server.h, web_page.h, IMU_ctrl.h, IMU.cpp}` and git
  history `f8fc989..d308df9`; committed build `General_Driver.ino.{bin,elf,map}`
  (ArduinoJson 7.0.4, arduino-esp32 2.0.14, PID_v2 2.0.1).
- Waveshare `UGV01_FACTORY.zip` and `UGV01_BASE.zip` (hashes above; the latter
  sha256 `5daf339df0a8ca879230d806b8d5d62d65703b4e243b4827682077770bbef4e5`),
  inspected and deleted; nothing from them is stored here.
- Waveshare wiki pages "UGV01" and "General Driver for Robots" (read 2026-10-02).
- ArduinoJson v6.21.5/v7.0.4, imax9000/Arduino-PID-Library 2.0.1, arduino-esp32
  2.0.14 and esp-idf v4.4.6 source, for number checks, PID and PWM behaviour.
- waveshareteam/ugv_rpi @ `3ae9f20` and ugv_jetson @ `18e9a24` (their default
  `main_type` 2 would put a UGV01 into open loop).

The project notes' example `{"T":1,"L":0.5,"R":0.5}` is the wiki's maximum and
would be full duty on an open-loop model: it is not a first bench command.
