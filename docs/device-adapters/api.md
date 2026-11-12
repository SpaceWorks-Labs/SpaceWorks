---
title: Adapter API reference
group: Reference
order: 62
summary: Every Device Adapter API v1 route with its request and response JSON.
---

# Adapter API reference (v1)

Base path: `/api/v1/device/adapter/v1/`. All routes are signed ([authentication](authentication.md)), JSON, and
validated against the schemas in [`schemas/`](schemas/) (the same dicts the server uses). Errors are
`{"detail": "...", "code": "..."}`; see [errors.md](errors.md).

## `POST hello`

```json
{ "protocol_version": 1, "adapter_kind": "fdm_printer", "vendor": "acme", "software_version": "1.4.2",
  "capabilities": [{ "name": "status", "version": 1 }, { "name": "control", "version": 1 }] }
```
Response `200`:
```json
{ "device_id": "...", "protocol_version": 1, "server_time": 1760000000, "config_version": 3, "poll_seconds": 15,
  "capabilities": [{ "name": "status", "version": 1 }], "unknown_capabilities": [],
  "bindings": [{ "id": "...", "target_type": "machine", "machine_id": 12, "target_id": "",
                 "external_ref": "printer-a", "capabilities": ["control", "events"] }] }
```
`adapter_kind` is one of `fdm_printer resin_printer laser cnc generic shelf_pointer label_printer scanner door sensor
kiosk`. Unknown capability names are returned in `unknown_capabilities`, never fatal. `config_version` rises when
staff bind or unbind a target; re-read `GET bindings` when it changes.

## `GET bindings`
`{ "bindings": [ ...as in hello... ] }`

## `POST status`
```json
{ "items": [{ "binding_id": "...", "observed_at": 1760000000, "state": "running", "progress_percent": 40,
              "power": "on", "busy": true, "error_codes": ["filament_runout"] }] }
```
`state`: `idle preparing running paused finished failed error offline maintenance` (`running` = busy/active).
Response: `{"results": [{"binding_id": "...", "result": "stored|stale|throttled|unknown_binding"}], "config_version": 3,
"server_time": ...}`. A report not newer than the stored one is `stale`; more than one per binding per 5 s is
`throttled`. Status is advisory: it never changes `Machine.status`.

## `POST events`
```json
{ "events": [{ "operation_id": "<uuid>", "binding_id": "<uuid>", "type": "maintenance.fault",
               "observed_at": 1760000000, "data": { "code": "hotend_clog", "severity": "fault", "detail": "..." } }] }
```
Up to 50 per call. Idempotent by `operation_id` (`{"result": "stored|duplicate"}`). The type must belong to a
capability the adapter declared (else `event_not_declared`) and, with a `binding_id`, to one that binding serves.
Server reactions: `maintenance.fault` is written to the machine's technical-fault log; `safety.area_cleared`
records the area-clear confirmation the access decision enforces; the rest are stored for staff.

## `POST commands/lease` and `POST commands/{id}/ack`
Lease returns `{"command": null}` or
```json
{ "command": { "command_id": "...", "binding_id": "...", "capability": "control", "command": "pause",
               "params": {}, "lease_token": "...", "lease_expires_at": 1760000300 } }
```
Ack: `{"lease_token": "...", "outcome": "succeeded|failed", "result_code": "ok"}`. At-least-once: an unacknowledged
lease expires and the command returns to the queue (bounded attempts, a TTL of ten minutes). A re-ack is idempotent. Every lease is audited as `devices.adapter_command_leased` (binding, command, capability,
command name and attempt; never the token or the params), next to `adapter_command_queued` (who asked) and
`adapter_command_acked`.
A command whose capability's child switch went off after it was queued is never leased (it fails with
`capability_switched_off`). Commands: `control` (`pause resume cancel power`), `door.access` (`unlock`),
`locate.indicate` (`indicate`), `locate.calibrate` (`aim jog`), `media.snapshot` (`snapshot`), `label.print`
(`print`), `diagnostics` (`log_bundle`), `job.dispatch` (`cancel_job`). Params match `schemas/command.*.json`.

## `POST access/authorize` (child switch `machines.integrations.access`)
```json
{ "binding_id": "...", "credential": { "type": "card_qr|nfc|pin", "value": "...", "member_number": "123", "pin": "..." } }
```
Response `200`: `{"allowed": true, "decision": "allowed", "reason": "ok", "max_seconds": 14400}` or
`{"allowed": false, "decision": "denied", "reason": "no_machine_access"}`.

Credentials (identification is not authentication):
- `nfc`: `value` is the tag id.
- `pin`: `value` is the PIN and `member_number` the number printed on the member card.
- `card_qr`: `value` is the member card's desk QR (32 hex characters) and `pin` the member's PIN. A card QR alone
  is refused with `pin_required` (prompt for the PIN and retry). A public card check link (`/verify/c/...`) or its
  bare token is never accepted: it is printed for anyone to verify a card, so it proves nothing about who holds it.

Every member-level failure (unknown tag, card or member number, no PIN set, wrong PIN, a locked or disabled
credential) answers the same `unknown_credential`, so a keypad cannot learn who has a PIN. Five wrong PINs in a row
still lock that member's PIN for 15 minutes (silently). Each binding (10) and each space (30) also has a budget of
failed PIN and card-QR attempts per 15 minutes; when it runs out, PIN and card-QR attempts there answer
`too_many_attempts` for a cooldown that doubles each time it trips within a day (5 minutes up to 24 hours), even
for a correct PIN. NFC is not budgeted. Reasons: `access.response.json` (`unknown_credential pin_required too_many_attempts
member_restricted membership_required waiver_acceptance_required presence_required no_machine_access machine_access_expired
machine_unavailable machine_in_use session_already_live booking_required booked_by_other maintenance_lockout
area_not_clear filter_alert internal_error_fail_closed ...`). The decision is the existing session rules (machine; a space manager's machine-access grant, decision 319 -- certifications no longer matter) or
active, unrestricted membership (door/space). A denial never changes a running session; any unexpected error is a
denial (`internal_error_fail_closed`). Every decision is an append-only log row and an audit row.

Bridges that map our reasons onto another system's refusal vocabulary (a Fabman-style bridge, for example) should
map `no_machine_access` to "member not authorised for this resource" and `machine_access_expired` to "authorisation
expired"; both are fixed by the space manager's grant, so the bridge shows "ask a space manager", not "get trained".

## `POST sessions/start` and `POST sessions/{id}/stop`
Start takes the same body as authorize and, when allowed, starts a machine session (source `device`) through the
machine-session service: `{"allowed": true, "session_id": 77, "max_seconds": 14400}` (denials as authorize). It needs
`machines.sessions` on. Stop: `{"reason": "member|device|idle", "active_minutes": 20, "idle_minutes": 2}` and only for a
session this adapter started; the usage entry and any charge are raised by the session service (charge-tracking ledger).

## `POST usage` (child switch `machines.integrations.usage_billing`)
An immutable usage record (`schemas/usage.log.json`), idempotent by `operation_id`: `{"result": "stored|duplicate"}`.

## Staff routes (`/api/v1/admin/`, MANAGE_DEVICES, machine scope)
These routes power the console's adapter area. In short: enroll through the device
routes with `kind: "adapter"`; `GET makerspace/{id}/adapters`, `GET adapters/{id}`, `POST adapters/{id}/bindings`,
`DELETE adapter-bindings/{id}`, `POST adapter-bindings/{id}/commands`, `GET adapters/{id}/commands|events`; poses,
aim, jog, indicate and position for shelf pointers; credentials; camera watch sessions.

### Console read-back and log lists
- `AdapterSummary` also carries `online: bool` (active, seen at least once, no open offline edge) and `offline_since:
  datetime|null` (null when online; for a never-seen adapter `online` is false and `offline_since` null). Each summary binding
  and every `Binding` response carries `config` (the binding's OWN overrides, `{}` if none) and `effective_config`
  (`{key: {"value": ..., "source": "type"|"binding"}}`: `type` = follows the machine-type profile, `binding` = overridden).
  Keys: `auto_off_idle_minutes, require_area_clear, max_session_minutes, require_filter_ok` (type or binding) and
  `auto_apply_terminal` (binding only, audited as `devices.adapter_auto_apply_set`).
- `PUT adapter-bindings/{id}/config` accepts all five keys and answers `200 {id, config, effective_config}`; an unknown key is 400.
- `GET adapters/{id}/access-decisions` -> DRF page `{count, next, previous, results: [{id, binding|null, member|null (user id
  only), credential_type, allowed, reason, session_id|null, created_at}]}`, newest first (page size 24, `?page=`). Filters:
  `binding` (uuid), `allowed` (true|false), `reason`, `credential_type`, `since`, `until` (ISO 8601 on `created_at`).
- `GET adapters/{id}/usage` -> DRF page of `{id, binding|null, operation_id, session_id|null, started_at, ended_at,
  active_minutes, idle_minutes, outcome, error_code, consumptions, created_at}`; filters `binding`, `outcome`, `since`, `until`.
- `GET adapter-bindings/{id}/jobs` (same path as the POST dispatch) -> DRF page of `{id, service_request_id, service_request_name,
  machine_name, state (awaiting|reported|applied|needs_review|cancelled), telemetry_state, progress_percent, telemetry_at,
  outcome, actual_minutes, percent_complete, failure_reason, reported_at, applied_at, created_at, command_status,
  command_attempts, command_error}`; filter `state`. Empty for a non-machine binding.
- All three need the `machines.integrations` switch, MANAGE_DEVICES in the space (machine scope for a binding), are 404 across
  tenants, and never return credential digests, PINs or member contact details.

### Paged lists
Every list marked "DRF page" above, plus `admin/adapter-bindings/{id}/artifacts`, `admin/adapter-bindings/{id}/detections`, the
job owner's `member/adapter-artifacts/requests/{id}` and `member/adapter-detections/requests/{id}` lists and the shelf-check history (`GET admin/makerspace/{id}/shelf-checks`), answers the standard DRF
page `{count, next, previous, results}` (page size 24 unless noted, `?page=`), not a bare array. The OpenAPI document
describes each as that envelope (`AdapterAccessDecisionPage`, `AdapterUsageRecordPage`, `AdapterBindingJobPage`,
`AdapterArtifactPage`, `AdapterDetectionPage`, `MemberAdapterArtifactPage`, `MemberAdapterDetectionPage`,
`ShelfCheckPage`). The unpaged lists (`adapters`, poses, credentials, config history, shelf locations) stay plain.

## Jobs (`job.dispatch`, `file.fetch`)
`POST jobs/lease` -> `{"job": null | {job_id, lease_token, lease_expires_at, binding_id, machine_id, service_request_id, has_files}}`;
`POST jobs/{id}/ack` (`schemas/job.ack.json`); `POST jobs/{id}/progress` (`job.progress.json`); `POST jobs/{id}/report`
(`job.report.json`, idempotent by `operation_id`, a different replay is 409; optional `profile_consumptions`
`[{key, quantity, attributes?}]` reports measured use by the machine type's consumable-profile key, e.g. `filament` in
grams, `sheet` in sheets, `thread` in 1,000 stitches; see [machine consumables](../how-to/machine-consumables.md)); `GET jobs/{id}/file` ->
`{files: [{file_id, name, content_type, size_bytes, kind, url}]}` (short-lived signed URLs, only while the job is
acknowledged). Staff: `POST admin/adapter-bindings/{id}/jobs {service_request_id}`; `PUT admin/adapter-bindings/{id}/config`
(`auto_off_idle_minutes`, `require_area_clear`, `max_session_minutes`, enforced by the server).

## Kiosk (`checkout.kiosk`, child switch `machines.integrations.kiosk`)
`POST kiosk/sessions`, `POST kiosk/sessions/{sid}/scan|evidence|issue|return`, `DELETE kiosk/sessions/{sid}`; schemas
`kiosk.*.json`. The credential follows the same rules as `access/authorize` (a card QR needs the member's `pin`).
A denied credential answers 201 with `allowed: false` and a reason; a member the self-checkout workflow refuses (not a
personal account, no current term, a guest pass that cannot borrow) gets that typed `4xx`, and the attempt is still
written to the access log. Every later call without a live session for this device is 404. The `evidence` call's
`size_bytes` is at most 10 MiB (`schemas/kiosk.evidence.json`, the default `EVIDENCE_MAX_BYTES`, the same ceiling the
presign enforces); a deployment that lowers the cap refuses a larger declared size with `413 artifact_too_large`.

## Media (`media.stream`, `media.snapshot`, child switch `machines.integrations.video`)
`GET|POST media/{watch}/signal` (schema `media.signal.json`; GET takes `?after=` and returns `ice_servers`),
`POST media/{watch}/snapshot` (`media.frame.json`), `POST media/{watch}/recording` (`media.recording.json`; needs
`machines.integrations.recording` and a watch opened with `record: true`). Viewer routes are under `member/adapter-watch/`.

## Media and data (decision 321)

Audio, two-way talk, artifacts, detections, telemetry history, diagnostics, the offline access cache, remote config and
signed time are specified in [media-and-data.md](media-and-data.md).

## Notifications
Needs attention, material runout, detections, session ending soon (member) and access denied (staff) go through the
notification catalogue (feature `devices`: `adapter_attention`, `adapter_runout`, `adapter_detection`,
`adapter_session_ending`, `adapter_access_denied`). A terminal job report that waits for staff review (every failed
report, and every report while `auto_apply_terminal` is off) tells staff once per job (`adapter_job_review`); the member
hears the outcome through the machine-service notices (`printing` `completed` / `failed`) when staff apply it.
Offline/recovered use the device state edges (a `status` call counts as liveness); maintenance due is the maintenance
schedule's. The full event list is in [notifications](../architecture/notifications.md).

## Webhook push (optional)
Staff: `PUT admin/adapters/{id}/webhook {url, include_data}` (public https only, port 443 or 8443; the secret `whsec_...`
is returned ONCE, on creation), `POST .../webhook/rotate` (new secret, shown once; the old one stops verifying), `GET .../webhook`,
`DELETE .../webhook`, `GET .../webhook/deliveries` (the delivery log). A push is a wake-up (`command.queued`, `job.queued`,
`config.changed`, `ping`; schema `webhook.envelope.json`), content-free unless `include_data` adds the capability and command
names; the work is still leased over the signed API. Verify `X-SpaceWorks-Signature: t=<unix>,v1=<hex>` where `v1` is
HMAC-SHA256 of `"<t>.<raw body>"` with the secret, and reject a `t` older than five minutes. Failed pushes retry with backoff
(30 s, 2 min, 10 min, 30 min, 1 h; six tries), and the endpoint disables itself after ten consecutive failed attempts
(re-saving it re-enables it). Each attempt claims the delivery under a 60-second lease, sends with a 5-second timeout and
no redirects, then records the result, so the same delivery is never sent twice at once; after a crash the lease
expires and the push is retried, which is why receivers should deduplicate on `X-SpaceWorks-Delivery`. A space with
adapters switched off sends nothing; its pushes wait and resume when it is switched back on. Each push resolves the host
name once, refuses it if any answer is not a public address, connects to that exact address (TLS still checks the
certificate against the name), reads at most 4 KiB of your reply and gives up after five seconds in total. The delivery
log says only delivered or failed (`last_error` = `delivery_failed`, or `url_refused` when the name stopped resolving to
a public address); it never shows the status code or network error of a failed attempt.

## Safety config and type profiles
`PUT admin/makerspace/{id}/machine-types/{type}/adapter-profile` sets defaults for every adapter binding on machines of that
type (`schemas/safety.profile.json`: `auto_off_idle_minutes`, `require_area_clear`, `max_session_minutes`,
`require_filter_ok`). `PUT admin/adapter-bindings/{id}/config` overrides any key for one binding and is the only place
`auto_apply_terminal` lives (`schemas/safety.config.json`): off by default, so every terminal report waits for staff; on, a
clean (completed) report goes straight through the workflow, and a failed one still goes to review. The setting is audited.
The sweep warns the member five minutes before `max_session_minutes`, then ends the session through the session service
(stop reason `max_length`) and queues `control power off`, exactly like idle auto-off. The sweep also runs in a
read-only space (it only powers a machine off or ends a session, which protects people); a paused space runs nothing.

## Shelf pointer poses and caps
Poses are validated by kind when saved (`schemas/pose.pan_tilt.json`, `pose.led_segment.json`, `pose.galvo_xy.json`; a pose
with no `kind` stays free-form, an unknown `kind` is `invalid_pose`). A binding's own config may set `laser_max_power_pct`
(1..100) and `max_on_seconds` (1..600); the server clamps every `indicate` and `aim` to them and `clear` is never capped.
See [hardware/shelf-pointer.md](hardware/shelf-pointer.md).

## Kiosk shelf light
When a kiosk scan finds a tool with a calibrated pose on a bound pointer, the server queues `locate.indicate` itself; the
scan response only says `"indicated": true|false` (poses and locations never leave the server).

## Not in this release
The usage-billing rate model.
