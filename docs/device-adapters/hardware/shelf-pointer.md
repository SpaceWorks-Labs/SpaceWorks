---
title: Build a shelf-pointer adapter (Raspberry Pi or ESP32)
group: Reference
order: 67
summary: What a Raspberry Pi or ESP32 shelf-pointer adapter must do at the API level, with message examples, the published pose kinds, the laser safety rules the server enforces, and a polling budget for small devices.
---

# Build a shelf-pointer adapter (Raspberry Pi or ESP32)

SpaceWorks ships **no** shelf-pointer firmware, wiring diagram or driver. It ships the **adapter API** that any pointer
speaks, and this page says what a Raspberry Pi or an ESP32 adapter has to do over that API. Read
[build an adapter](../build-an-adapter.md) first for the general loop, [authentication](../authentication.md) for
signing and [errors](../errors.md) for the typed codes. For what staff do with a pointer see the
[shelf pointer how-to](../../how-to/shelf-pointer.md).

## What real pointers look like (research summary)

The API was shaped by how existing pointer and pick-to-light builds work. Sources are linked so you can check them;
a few facts below come from general practice and are marked.

**Laser on pan/tilt servos (Raspberry Pi or ESP32).** The common build is two hobby servos (pan and tilt) driven by a
PCA9685 16-channel PWM board over I2C, with a small laser module switched by a GPIO pin or transistor. Waveshare and
DFRobot sell a ready-made 2-DOF Pan-Tilt HAT with an on-board PCA9685
([Waveshare](https://www.waveshare.com/wiki/Pan-Tilt_HAT), [DFRobot FIT0731](https://wiki.dfrobot.com/Pan_Tilt_Hat_For_Raspberry_Pi_SKU_FIT0731)).
A guide to the PCA9685 on a Pi says to power the servos from a separate supply, never the Pi's 5 V pin
([Zbotic](https://zbotic.in/pca9685-servo-shield-raspberry-pi-16-servos/)). A Pi 5 pan-tilt laser project drives the
laser at 50 % power for eye safety ([cat-toy build](https://exyxyz.notion.site/web-cat-2ae3a2250b7f802f8c28d8c3f5631774)),
and the ROS wiki documents the two-servo pan-tilt control loop ([ROS](https://wiki.ros.org/Drivers/Tutorials/ControllingAPan-tiltKitUsingTwoServoMotorsPython)).
This is why the first pose kind is `pan_tilt` in **degrees** with an optional `laser_power_pct`.

**Galvo scanners (ESP32 with a DAC).** Mirror galvos are driven by a 12 or 16-bit SPI DAC (MCP4822, DAC8562), not the
ESP32's own DAC: [GalvOS](https://github.com/Andre1Becker/GalvOS) (ESP32-S3, DAC8562), the
[ILDAWaveX16](https://www.tindie.com/products/stanleyprojects/ildawavex16-v2/) (blanks the laser and holds position on a
data underrun), the [UC2 galvo add-on](https://openuc2.github.io/archive/galvo-addon/reference) and an
[Arduino galvo tutorial](https://instructables.com/Arduino-Laser-Show-With-Real-Galvos). They are real but rarer and more
expensive than servos for a shelf, so `galvo_xy` exists as a third, normalised kind (`-1..1`) and the DAC scaling stays
on the adapter.

**Pick-to-light with LED strips.** Warehouse pick-to-light and put-to-light systems light a segment per bin
([Modula overview](https://modula.us/blog/pick-to-light-systems/)). Open builds use addressable WS2812 strips: a
[Wemos D1 battery pick-to-light device with WS2812B and a JSON protocol](https://hackster.io/matthew-champion/warehouse-management-pick-to-light-device-9e0d8a),
an [ESP32 put-to-light project](https://github-users.yhajoa.workers.dev/nessergio/ptl) and the [WLED](https://awesome.ecosyste.ms/projects/github.com%2Fwled%2Fwled)
firmware. A shelf is a run of pixels, so the second kind is `led_segment {strip, start, count, color}`.

**Calibration.** There is no standard. Published methods map camera pixels to angles with a homography
([DIJIT](https://arxiv.org/pdf/2512.07998), a [laser-voltage homography](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10798339),
[Tworek et al.](https://www.robotcub.org/misc/papers/08_Tworek_Bernardino_SantosVictor.pdf)) or fit a full camera-to-gimbal
model ([patent family](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11120392)). A homography works
best when the target is roughly planar, which a shelf face is. The simplest robust method for a shelf wall is the one
this API uses: **jog the pointer by eye to each shelf and save the pose that landed there**. Any fitted model stays on the
adapter; the server stores only the resulting pose, never reference points, so the API needs no calibration-assist data.

**Laser safety.** Class 2 visible lasers (up to 1 mW) rely on the 0.25 s blink reflex; Class 3R visible lasers go up to 5 mW
and can exceed the eye limit even for brief exposure, though the risk is judged low ([LaserMet](https://www.lasermet.com/us/?p=1175),
[Seibersdorf IEC 60825-1 notes](https://www.seibersdorf-laboratories.at/fileadmin/user_upload/docs/le/las/publ/whitepaper_iec-60825-1.pdf),
[LBNL classes](https://ehs.lbl.gov/resource/documents/radiation-protection/laser-safety/laser-classification-explan)). The search did not reach
the standard text itself: check exact limits against IEC 60825-1 and your local rules. Use a Class 2 module, never aim
across walkways at eye height, and keep the on-time short. The API therefore has a hard on-time and power cap.

**What an ESP32 can do.** Ed25519 and SHA-256 are all the signing needs. [Monocypher](https://rust-digger.code-maven.com/src/monocypher-sys-4.0.2/Monocypher/README.md)
ships Ed25519 and SHA-512 as optional files and is about the size of TweetNaCl; Espressif's [libsodium component](https://components.espressif.com/components/espressif/libsodium/versions/1.0.20~3/readme)
covers it too (the ESPHome port compiles only verification, not signing, so use the full one). TLS comes from mbedTLS in
ESP-IDF. The search found nothing on ArduinoJson or HTTPS heap use, so **measure on your board**: every payload below is
small (under 1 KiB), so a 1 KiB JSON document is enough.

## The shape of the API

A pointer adapter declares `locate.indicate` and (to be calibrated) `locate.calibrate`, optionally `config.push` and
`time.sync`, and is **bound** to a target: a `space` (the whole wall), or a `storage_location`, `item` or `box`.

```json
POST /api/v1/device/adapter/v1/hello
{ "protocol_version": 1, "adapter_kind": "shelf_pointer", "vendor": "acme", "software_version": "1.0.0",
  "firmware": "esp32-1.0.0", "health": "ok",
  "capabilities": [{"name":"status","version":1},{"name":"locate.calibrate","version":1},
                   {"name":"locate.indicate","version":1},{"name":"time.sync","version":1},{"name":"config.push","version":1}] }
```

Every call is signed with Ed25519 ([authentication](../authentication.md)). The signed message is the SHA-256 of the body
plus method, raw target, timestamp and nonce, so a pointer needs exactly Ed25519 sign and SHA-256.

### Pose kinds (published JSON Schemas)

A pose is the small flat object staff saved for one location, item or box. The server validates it when it is saved and
returns it to the **owning** adapter inside the `indicate` command. Schemas are in [`../schemas/`](../schemas/):

| `kind` | Fields | Schema |
|---|---|---|
| `pan_tilt` | `pan_deg`, `tilt_deg` (-180..180), optional `laser_power_pct` (0..100) | `pose.pan_tilt.json` |
| `led_segment` | `strip` (0..15), `start` (0..4095), `count` (1..512), optional `color` (name or `#rrggbb`) | `pose.led_segment.json` |
| `galvo_xy` | `x`, `y` (-1..1, normalised), optional `laser_power_pct` | `pose.galvo_xy.json` |

A pose with **no** `kind` is still allowed and stays free-form (declare your own `calibration_schema` in hello). A pose
with an **unknown** `kind` or one that fails its schema is refused (`invalid_pose`), so a typo never reaches a laser.
A Pi that drives servos and an LED strip uses two bindings, or sends a `led_segment` pose for shelves that have strips.

### The loop (what to implement)

1. **Enroll** with the one-time token, then **hello** and `GET bindings` (small, no poses in either).
2. **Clock.** Requests must be within 300 s of the server. A Pi has NTP. An ESP32 should use SNTP; without it, seed the
   clock from the `Date` header of any HTTPS response (even a `401`), then confirm with the signed `GET time?nonce=`.
3. **Poll** every `poll_seconds` (15 by default): `POST status` per binding, then `POST commands/lease`.
4. **Execute** the leased command and `POST commands/{id}/ack` within the lease (60 s by default).
5. **Calibration** commands: `aim {pose}` moves the head to a candidate pose; `jog {dx, dy}` nudges it. After a move,
   send a `calibration.position {session_id, pose}` event so the console shows where the head really is. Nothing is saved
   until staff press save (`PUT poses`).
6. **Config push.** Staff push servo limits and offsets with `config.push`; fetch `GET config`, apply, and `POST config/ack`.
   Keys that look like secrets are refused, so keep Wi-Fi passwords and keys on the device.

```json
POST commands/lease  ->  200
{ "command": { "command_id": "6f1c1f0e-...", "binding_id": "6f1c1f0e-...", "capability": "locate.indicate",
    "command": "indicate",
    "params": { "mode": "point", "duration_seconds": 15,
                "pose": { "kind": "pan_tilt", "pan_deg": -12.5, "tilt_deg": 33.25, "laser_power_pct": 30 } },
    "lease_token": "...", "lease_expires_at": 1760000060 } }

POST commands/6f1c1f0e-.../ack   { "lease_token": "...", "outcome": "succeeded" }
```

```json
indicate with an LED strip:
"params": { "mode": "light", "duration_seconds": 20,
            "pose": { "kind": "led_segment", "strip": 1, "start": 24, "count": 6, "color": "#00ff66" } }

clear (always allowed, never capped, no pose):
"params": { "mode": "clear" }
```

```json
POST config/ack   { "version": 4, "outcome": "applied" }
GET config  ->  { "version": 4, "config": { "pan": {"min_deg": -60, "max_deg": 60, "offset_deg": 1.5},
                                              "tilt": {"min_deg": -30, "max_deg": 45}, "servo_us": {"min": 500, "max": 2500} } }
GET time?nonce=q7Zr2LmX9wPa4TcY  ->  { "server_time": 1760000000, "nonce": "q7Zr2LmX9wPa4TcY", "kid": 2, "signature": "<hex>" }
```

### Safety (server-enforced and adapter-kept)

Staff set two caps per pointer binding (`PUT admin/adapter-bindings/{id}/config`, `schemas/safety.config.json`):
`laser_max_power_pct` (1..100) and `max_on_seconds` (1..600). **The server applies them to every command it builds**, from
the console, "Show on shelf" and kiosk scans:

- `duration_seconds` is lowered to `max_on_seconds`. A laser pose (`pan_tilt`, `galvo_xy`) with **no** configured cap
  still stops after **60 seconds**.
- `laser_power_pct` in the pose is lowered to `laser_max_power_pct`, and set to it when the pose carries none.
- `clear` is **never** capped, delayed or rate limited.

An adapter must still keep its own safe defaults, because a server can be wrong or unreachable:

- Switch the laser off when `duration_seconds` ends, on boot, on a watchdog timeout and on any `clear`.
- Never exceed the `laser_power_pct` you were given; never turn on from a command whose lease has expired.
- Start with the laser off and **blank the laser while the head moves** (as the ILDAWaveX16 does on underrun).
- If it cannot reach the server it keeps its on-time; it does not hold a laser on "until told".

### Offline and backoff

Poll with a fixed interval while healthy. On a network error or `5xx`, back off exponentially with jitter (1, 2, 4 ... capped
at 60 s) and reset on success. On `401` check the clock before retrying (skew is the usual cause). On `423` (the space is
frozen for migration) wait 60 s. On `404` the space switched integrations off: stop polling for 5 minutes. A command
the pointer never leased expires on the server, so reconnecting never replays stale "point" commands.

### Payload sizes and polling budget

Measured from the exact message shapes for a pointer with about **200 saved poses** (poses are never in hello or bindings;
they travel only inside one `indicate` command, one at a time). Compact JSON, bytes of body (signing headers add about
350 more):

| Message | Bytes |
|---|---|
| hello request / response | 359 / 816 |
| `GET bindings` | 198 |
| `POST status` (one binding) | 105 |
| `POST commands/lease`, nothing waiting | 16 |
| `POST commands/lease`, an indicate command | 388 |
| `POST commands/{id}/ack` | 83 |
| `GET config` (servo limits) | 203 |
| `GET time` | 204 |

If the 200 poses were (wrongly) sent in hello they would add about 14.8 KB; they are not. A test
(`backend/tests/shelf_pointer/test_shelf_checks_and_budget.py`) asserts these stay small and prints the real sizes.

At the default 15 s interval a pointer makes 4 `lease` and 4 `status` calls a minute, about 480 requests an hour and well
under 1 MB a day including headers. A pointer that registers a **webhook** (see [api](../api.md)) can poll every 60 s and
lease only when the wake-up arrives; the push carries no pose.

## Testing without hardware

The conformance kit has a simulated pointer (`backend/tests/adapter_conformance/sim_shelf_pointer.py`): it speaks the real
signed protocol, records what it would point at, honours the on-time and auto-clears. It is a **test helper, not a
standalone adapter**. Use it as a reference for the command handling above.
