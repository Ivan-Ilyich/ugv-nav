# UGV01 controller protocol (host adapter reference)

Written **2 October 2026** from firmware source and vendor docs; adapter in
`src/ugv_nav/ugv01/`. All of it is from source unless marked measured.

## Firmware identity

| Item | Finding |
| --- | --- |
| Source | [waveshareteam/ugv_base_general](https://github.com/waveshareteam/ugv_base_general), sketch `General_Driver/`, ESP32-WROOM-32 |
| Revision read | `d308df91b333a513f45a238bef9ba9a0a5edf64c` (2025-11-28, OLED `version: 0.95`). `uart_ctrl.h`, `movtion_module.h`, `json_cmd.h`, `ugv_config.h` unchanged since `f8fc989` (2024-03-24, `version: 0.90`) |
| Licence | GPL-3.0; host apps `ugv_rpi` GPL-3.0, `ugv_jetson` AGPL-3.0. Only protocol facts were taken; **no firmware or host code is copied here** |
| Factory image | `UGV01_FACTORY.zip` (sha256 `4aed26aa7001d80ba53ecec182800f92e39398af182b478ba0d769b2fd67d3cd`), app `bin/UGV01_V0.9.ino.bin` (sha256 `493084393c32c6177971d4726b94e8d9fb159d1efbe03bf9f40d9d2185655113`): same family, `version: 0.90` |
| Robot model | `mainType` 3 = UGV01, the only closed-loop (PID, m/s) path. On this board a 0.05 m/s command read back about 0.05 m/s on the board's own estimate (measured on the floor), as closed loop should. GitHub HEAD compiles 1 (open loop), so a reflash from HEAD would silently change the speed unit |
| This board | Version not read. Its replies (`"y":"null"`, no `temp`; measured) match builds from `b113287` (May 2024) to mid-2024, all labelled 0.90. `T:130` does not refresh its heartbeat (measured), so it is not `UGV01_BASE.zip`, an older, incompatible firmware (1,000,000 baud, `{"T":0}` stop, heartbeat refreshed by any JSON) |

## Link and framing

- **Wi-Fi (in use since 19 October):** `GET http://<host>/js?json=<command>`, reply in
  the HTTP body. No echo or unsolicited output. `T:407` (Wi-Fi mode) restarts the
  board's Wi-Fi and blocks up to 15 s, so no HTTP reply arrives. On 19 October a
  first attempt sent the AP password under a wrong key, which leaves the access
  point without a password; check the `T:405` reply afterwards.
- **Serial (not used):** UART0, **115200 8N1**, by the 40-pin header or USB-C
  (Waveshare says it needs disassembly). USB-C goes through a CP2102 whose DTR/RTS
  drive the ESP32 reset and boot pins, so opening it may reboot the board.
- **Host to board:** one JSON object per line ending in `\n`; selector key `"T"`
  (integer). No ACK, NAK or checksum; parse errors are dropped silently.
- **Board to host (serial):** CRLF JSON lines, mixed with an echo of every parsed line
  (printed *before* the command runs), plain debug text, and a T:405 Wi-Fi status with
  **no newline** that can contain plaintext passwords. The parser extracts JSON from
  any text and never raises. The probe redacts passwords, SSIDs, MAC and IP addresses.
- **Boot (serial):** any byte received before the boot mission ends (several seconds;
  longer in Wi-Fi STA mode) aborts it; with debug text on, `[missionPlay finished.]`
  marks the end.

## Commands the adapter sends

| JSON | Meaning | Notes |
| --- | --- | --- |
| `{"T":1,"L":l,"R":r}` | Track speeds | m/s on the closed-loop path; positive = forward (both tracks, measured). Both must be numbers, or it is a silent no-op. `abs(value) > 2.0` is **ignored, not clamped**. Open-loop types read duty/512 (0.5 = full on) |
| `{"T":1,"L":0.0,"R":0.0}` | Normal stop | A PID decel, not a brake |
| `{"T":130}` | One T:1001 reply | Does not refresh the heartbeat (measured) |
| `{"T":126}` | One T:1002 reply (probe only) | |
| `{"T":139}` | Speed-rate reply (probe only) | Per-side multiplier, 0..1 |

Deliberately **not** sent: `T:0` (no-op here), `T:115` (not a stop on this path), `T:11`
(unclamped PWM; disables the PID, leaves a stale integrator), `T:13`, and every
configuration command (`T:2` PID gains, `T:111` blocking delay, `T:136` heartbeat period,
`T:900` robot model, `T:131/142/143/605` stream/echo/debug, `T:600/604` reboot/erase,
file, mission, Wi-Fi and ESP-NOW writes).

## Feedback the adapter parses

| Reply | Fields (units) | Caveats |
| --- | --- | --- |
| T:1001 | `L`, `R` track speed (m/s); `r`, `p`, `y` (deg); `v` battery (V); `temp` ESP32 die (°C) | Per-loop estimate, in steps of about 0.025 m/s when no `T:1` is being sent (measured; 0.03 computed). No timestamp or encoder counts, so stamped with host monotonic time at receipt. `v` can be 10 s stale. `temp` absent before mid-2024 builds. Builds from `b113287` (May 2024, still labelled 0.90) send `"y":"null"`; earlier 0.90 builds and later ones send a number. IMU frame and yaw calibration unknown |
| T:1002 | `ax..az` (mg), `gx..gz` (deg/s), `mx..mz` (~µT), `r`, `p`, `y` (deg) | Sensor frame; chassis mapping unknown |
| T:139 | `L`, `R` multipliers (0..1) | |

`valid` is false when a speed is missing, non-numeric, non-finite or above 2.5 m/s
(open-loop types can report PWM counts there).

## Safety behaviour

### Firmware (from source; heartbeat measured)

- **Heartbeat:** 3000 ms. Refreshed only by `T:1` (when L and R are numbers, before the
  range check, so an ignored out-of-range `T:1` still refreshes it), `T:11` and `T:13`,
  from any source (serial, HTTP, ESP-NOW, missions). On expiry it sets setpoint 0 once
  and does not latch, so the next motion command resumes motion. Measured: the tracks
  stopped 3.26 s after the last `T:1`
  ([result](hardware.md#first-guarded-drive-6-november-2026)).
- **No latched emergency stop.** The physical backstop is the power switch.
- **What weakens it:** `T:136` with a negative value disables it; anything blocking the
  loop (`T:111`, missions) holds the last duty; an open web-UI tab resends its last
  `T:1` every 1.5 s; `T:2` with zero gains freezes the integrator. Wi-Fi
  (unauthenticated `/js`) and ESP-NOW from any sender can inject motion.
- **Start-up:** motor pins are undefined for roughly the first 1.5-4 s of boot; the
  heartbeat fires once at about 3 s uptime.

### Host adapter (this repo)

| Decision | Choice | Reason |
| --- | --- | --- |
| Speed limit | Default cap **0.10 m/s**, up to 0.5 m/s | 20 % of the wiki range |
| Out-of-cap / NaN / inf | **Reject**, never clamp; guard disarms | A caller bug; clamping would change the turn ratio |
| Command lease | **0.5 s** (0.05-1.0 allowed), on the client's monotonic clock | A stale command runs about 0.5 s (5 cm at the default cap) before the client stops it; the stop itself took 0.26 s at 0.05 m/s (measured on the floor) |
| Send rate | **10 Hz** motion + T:130 poll | Matches the PID's 100 ms sample; ~12 % of the serial link with echoes |
| Link health | Up while valid T:1001 is ≤ 0.5 s old | Invalid feedback or an echo never counts. On serial it is round-trip evidence only if nothing else triggers T:1001 (`unsolicited_base_feedback` checks this) |
| Stop | Written at once; resent for 1 s and while feedback shows motion; then quiet | Quiet lets the heartbeat act as backstop |
| Re-arm | Explicit `arm()` plus a new command after any stop or fault | No stale command can resume; arming needs a live link |
| Reconnect | Stop written at once when the link returns | Stops sent during an outage never arrived |

If the host itself fails, stopping depends on the heartbeat. "Stationary" means a
reading of exactly 0, which can also appear while creeping. The simulator is idealised.

## On the robot

Measured so far: [first contact](hardware.md#ugv01-first-contact-19-october-2026) and
[first guarded drive](hardware.md#first-guarded-drive-6-november-2026); the facts
they confirm are marked "measured" above.

Not yet measured: the firmware version; side mapping and real track width; loop
period; floor stop and overshoot, and any lurch on resume; a real Wi-Fi loss;
drivetrain constants (from source: wheel diameter 0.0523 m, 1092 counts/rev, track
width 0.141 m). Serial only: baud, device node, DTR/RTS reset, echo defaults, cable
pull.

## Sources

ugv_base_general @ `d308df9`: `General_Driver/{General_Driver.ino, uart_ctrl.h,
json_cmd.h, movtion_module.h, ugv_config.h, ugv_advance.h, wifi_ctrl.h, esp_now_ctrl.h,
http_server.h, web_page.h, IMU_ctrl.h, IMU.cpp}`, history `f8fc989..d308df9`, build
`General_Driver.ino.{bin,elf,map}` (ArduinoJson 7.0.4, arduino-esp32 2.0.14, PID_v2
2.0.1). `UGV01_FACTORY.zip` (hashes above) and `UGV01_BASE.zip` (sha256
`5daf339df0a8ca879230d806b8d5d62d65703b4e243b4827682077770bbef4e5`), inspected and
deleted. Waveshare wiki (read 2026-10-02). ArduinoJson v6.21.5/v7.0.4,
imax9000/Arduino-PID-Library 2.0.1, esp-idf v4.4.6. waveshareteam/ugv_rpi @ `3ae9f20`,
ugv_jetson @ `18e9a24` (their default `main_type` 2 would put a UGV01 into open loop).
