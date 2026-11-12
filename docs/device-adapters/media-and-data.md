# Media and data capabilities (decision 321)

Everything here is **API only**. SpaceWorks core stores, serves and notifies; it never decides what to do about
a detection, a temperature or an offline decision (decision 320). Rules and automation live in the adapter.
Every capability has a child switch under `machines.integrations` (all off by default; the routes answer `404`
while off), a JSON Schema in [`schemas/`](schemas/), OpenAPI entries, conformance coverage
(`tests/adapter_conformance`, `run_media`) and tests in `backend/tests/parity_0120/adapter_media/`.

| Capability | Switch | Adapter routes (`/api/v1/device/adapter/v1/`) | Staff / member routes |
| --- | --- | --- | --- |
| `media.audio` | `.audio` | audio track in the existing `media/{watch}/signal` SDP; `announce_audio` in the poll reply | staff watch body `audio: true` |
| `media.talk` | `.talk` | `ptt_on` / `ptt_off` arrive as viewer signals | `POST member/adapter-watch/{id}/talk {active}` |
| audio recording | `.audio_recording` | `POST artifacts` kind `audio_recording` | watch body `record + audio + notice_ack` |
| `artifact.upload` | `.artifacts` | `POST artifacts`, `POST artifacts/{id}/complete` | `GET admin/adapter-bindings/{id}/artifacts`, `GET admin/adapter-artifacts/{id}/url`, member `GET member/adapter-artifacts/requests/{id}` and `.../{id}/url` |
| `detection.report` | `.detections` | event `detection.reported` | `GET admin/adapter-bindings/{id}/detections`, member `GET member/adapter-detections/requests/{id}` |
| `telemetry.history` | `.telemetry_history` | none (the server stores `status.telemetry` and `sensor.reading`) | `GET admin/adapter-bindings/{id}/telemetry` |
| `diagnostics` | `.diagnostics` | `diagnostics` block in status; hello `firmware`, `health`; command `log_bundle` | `POST admin/adapter-bindings/{id}/log-bundle` |
| `access.cache` | `.offline_cache` | `GET access/cache?binding_id=`, `POST access/offline-decisions` | cache status inside `GET admin/adapters/{id}` |
| `config.push` | parent | `GET config`, `POST config/ack` | `GET/POST admin/adapters/{id}/config-versions` |
| `time.sync` | parent | `GET time?nonce=` | none |

## Audio and two-way talk

Audio is a track on the existing `media.stream` WebRTC session, **receive-only by default**: the viewer opts in per
watch and the adapter is told (`audio`, `talk`, `announce_audio` in the signal poll). Audio is more sensitive than
video, so three separate switches exist: listen (`.audio`), talk (`.talk`) and record (`.audio_recording`).

- **Privacy notice at the device.** When `announce_audio` is true the adapter must make it perceptible at the
  location (a chime, a light, a sign). The console shows the viewer the same notice.
- **Talk** is staff only (MANAGE_DEVICES and machine scope), push-to-talk, relayed as `ptt_on` / `ptt_off` signals,
  capped at 200 presses per watch; each press and release is an audit row. The job-owner watch never has audio or talk.
- **Recording audio** needs the `.audio_recording` switch, `notice_ack: true` on the watch, and an adapter upload of
  kind `audio_recording` during that watch. Retention is three days (video recordings: seven).

```mermaid
sequenceDiagram
  participant S as Staff browser
  participant C as SpaceWorks
  participant A as Door adapter
  S->>C: POST admin/adapter-bindings/{id}/watch {audio, talk}
  C-->>S: watch (audio, talk, expires_at); audit adapter_audio_started
  A->>C: GET media/{watch}/signal  (announce_audio=true: chime at the door)
  S->>C: POST member/adapter-watch/{w}/signal offer
  A->>C: POST media/{watch}/signal answer
  S->>C: POST member/adapter-watch/{w}/talk {active:true}
  C-->>A: signal ptt_on (audit adapter_talk_started)
  S->>C: POST .../talk {active:false}
  C-->>A: signal ptt_off (audit adapter_talk_stopped)
```

## Artifacts

Timelapses, job thumbnails and previews, failure snapshots, log bundles and audio clips are **private** objects.
`POST artifacts` declares `{operation_id, binding_id, kind, content_type, size_bytes, service_request_id?, session_id?,
command_id?}` and returns a presigned upload that lands on the **staging** key; `POST artifacts/{id}/complete`
checks the real size and promotes it once. Per kind:

| Kind | Max size | Retention (default) | Content types |
| --- | --- | --- | --- |
| `thumbnail`, `preview` | 5 MB | 90 days | jpeg, png, webp |
| `failure_snapshot` | 5 MB | 30 days | jpeg, png, webp |
| `timelapse` | 256 MB | 30 days | mp4, webm |
| `log_bundle` | 10 MB | 7 days | gzip, zip, text |
| `audio_recording` | 64 MB | 3 days | ogg, webm, mpeg, wav |

Retention is overridable per kind with the setting `ADAPTER_ARTIFACT_RETENTION_DAYS`. The limit key
`adapter_artifacts` (default none) refuses only the start of a new artifact (`409 adapter_artifacts_quota_reached`).
Staff in the machine scope read artifacts through short-lived URLs; the **job owner** reads their own job's
thumbnails, previews, timelapses and snapshots (never audio or log bundles). Opening audio or a log bundle is audited.
A sweep (Celery, every ten minutes) deletes bytes at expiry and abandoned uploads after two hours; the row stays as
a `purged` marker. A space purge deletes the objects first.

## Detections

`detection.reported` `{kind: failure|spaghetti|fire|smoke|person|other, confidence 0..1, artifact_id?, note?}` is stored
as the append-only event and notifies staff and the job owner of the in-progress job on that machine through the
`devices` catalogue (`adapter_detection`, once per binding and kind per five minutes, preferences respected). The
evidence frame is an `artifact_id` of this binding. Admission is rate limited (30 per binding per ten minutes, `429
rate_limited`). **Core never pauses, powers off or cancels.** The job owner sees kind, confidence and time, not the note.

## Telemetry history

Numeric `status.telemetry.temperatures/metrics` and `sensor.reading` events become series (`temp.*`, `metric.*`,
`sensor.*`). Raw samples are kept 24 hours, then rolled into one-minute buckets (7 days), then fifteen-minute buckets
(90 days), then deleted; every rollup keeps avg/min/max/count. Settings: `ADAPTER_TELEMETRY_RAW_HOURS`,
`ADAPTER_TELEMETRY_MINUTE_DAYS`, `ADAPTER_TELEMETRY_QUARTER_DAYS`. The staff read route picks the finest resolution that
covers `since` (override with `resolution=0|60|900`) and returns at most 2000 points.

## Diagnostics

Hello and status carry `firmware`, `health` (`ok|degraded|failing`), uptime and last error code. `POST
admin/adapter-bindings/{id}/log-bundle` queues the `diagnostics.log_bundle` command `{max_bytes, since_seconds}`; the
adapter leases it, then uploads with `kind: log_bundle` and the leased `command_id` (a bundle is accepted only for an
open request). Bundles are private, seven days and capped at 10 MB.

## Offline access cache

```mermaid
sequenceDiagram
  participant A as Door adapter
  participant C as SpaceWorks
  A->>C: POST hello
  C-->>A: cache_keys [{kid, public_key (Ed25519), status}] (public keys only)
  A->>C: GET access/cache?binding_id=B
  C-->>A: {kid, version, issued_at, expires_at, entries:[{digest,type:nfc}], signature}
  Note over A: network lost: decide from the verified, unexpired list only
  A->>C: POST access/offline-decisions {decisions:[...]}
  C-->>A: results (stored | duplicate | rejected); written to the access log with offline=true
```

- **Digests only.** The list holds the tenant-keyed HMAC digests of NFC credentials. No PINs, names or member ids.
  A digest is listed only for an active, unrestricted member and, for a machine binding, when the single machine-access
  function `machines.access_grants.can_use` allows. Standing, presence, booking and supervision are online-only
  rules: an adapter that needs them must fail closed offline.
- **Short TTL**: 15 minutes by default (binding config `offline_cache_ttl_seconds` 60..86400, or the setting
  `ADAPTER_ACCESS_CACHE_TTL_SECONDS`). A revoked credential or grant disappears at the next sync. The list never
  outlives a machine-access grant it lists: `expires_at` is the earliest end of a listed member's grant, and a grant
  ending within a minute is left out (so a list can be shorter-lived than the TTL).
- **Signature (asymmetric)**: Ed25519, hex-encoded (128 chars), over FRAMED bytes so a signature for one purpose can
  never be replayed as another (the cache and the signed time share the key). Framing: the ASCII domain, one `0x00`
  byte, then for each field a 4-byte big-endian length and the field's UTF-8 text (integers in decimal). The cache
  domain is `spaceworks-adapter-offline-cache-v1` and the fields, in order, are `binding_id`, `kid`, `version`,
  `issued_at`, `expires_at` and the lowercase hex SHA-256 of the sorted digests joined by a comma. Example (Python):
  `b"spaceworks-adapter-offline-cache-v1\x00" + b"".join(len(f).to_bytes(4, "big") + f for f in fields)`.
  The server key is derived with HKDF-SHA256 from the deployment `SECRET_KEY` per key version; `hello` returns only the
  PUBLIC keys as `cache_keys: [{kid, public_key (base64), status: current|previous}]`. No secret ever leaves the server, so a
  holder of the adapter's data cannot forge a cache. The adapter picks the key by `kid`, must reject an unknown `kid`, a bad
  signature or an expired list.
- **Rotation**: raise the setting `ADAPTER_CACHE_KEY_VERSION`. New caches are signed with the new `kid`; `hello` lists the
  previous key as `previous` for `ADAPTER_CACHE_KEY_GRACE_DAYS` (default 7) after `ADAPTER_CACHE_KEY_ROTATED_AT` (epoch), so caches
  issued earlier stay verifiable until they expire (caches live minutes). Adapters should re-fetch `cache_keys` at every hello.
- Up to 5000 entries per binding (`409 cache_too_large`).
- **Reporting offline decisions**: `POST access/offline-decisions` stores each decision once (by `operation_id`). A
  `decided_at` more than five minutes in the future refuses the batch (`400 observed_in_future`); one older than
  7 days is not stored and answers `{"result": "rejected", "code":
  "decided_too_old"}`. The receive time is recorded in the audit log. An ALLOW whose digest was not a live credential
  of this space at that time, reported with no cache ever issued, or after the last issued cache had expired is still
  stored but audited as flagged (`devices.adapter_offline_decision_flagged`) for staff review.
- **`SECRET_KEY`**: the signing keys, every stored NFC/PIN digest and every derived webhook secret come from the
  deployment `SECRET_KEY`. Rotating it re-keys adapters at their next hello and invalidates every enrolled tag and PIN
  (staff must set them again); rotate it only when it has leaked.

## Remote config and time

Staff `POST admin/adapters/{id}/config-versions {config}` (a JSON object up to 16 KiB; keys that look like secrets are
refused: keep passwords and tokens on the adapter). The adapter sees `config_version` change in every status reply,
fetches `GET config` and answers `POST config/ack {version, outcome: applied|rejected, detail?}`; the console shows the
last versions and their acknowledgements. `GET time?nonce=` returns `{server_time, nonce, kid, signature}`. The adapter MUST send a fresh random nonce of 16 to 64
characters from `A-Z a-z 0-9 _ -` (otherwise `400 invalid_nonce`; the server never invents one) and check that the
reply echoes it. The signature is Ed25519 (hex) with the same server key (`kid` in the reply) over the framed bytes
of domain `spaceworks-adapter-time-v1` and the fields `nonce`, `kid`, `server_time` (framing as for the cache above). Note: the call itself is a signed device request, so it can
only be made within the protocol's timestamp tolerance; every status reply also carries `server_time`.

## Privacy summary

Audio and talk are staff only, separately switched and audited; audio recording needs an acknowledged notice and keeps
three days. All artifacts are private, retention-limited and purged with the space. Offline caches hold digests only.
Detections notify and never act. Nothing in this document is public or reachable without the switch, the machine scope
and, for the owner routes, ownership of the job.
