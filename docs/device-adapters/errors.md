---
title: Adapter error codes
group: Reference
order: 63
summary: The typed error codes of the Device Adapter API and what an adapter should do for each.
---

# Adapter error codes

Every refusal is JSON `{"detail": "...", "code": "..."}` (a typed `code` is present on adapter-specific refusals;
authentication failures and the few refusals inherited from the printer job path carry only `detail`). `errors` (a
list of `path: message`, never a submitted value) is added to `invalid_payload`; `artifact_too_large` adds `max_bytes`
when the declared size is refused; `event_not_declared` adds `event_type`.

New codes may appear in a later release (see [versioning](versioning.md)): treat an unknown `code` by its HTTP status.

## Adapter routes (`/api/v1/device/adapter/v1/`)

| HTTP | `code` | Where | Meaning | Adapter action |
|---|---|---|---|---|
| 400 | `invalid_payload` | any body or query | The body does not match the published JSON Schema (unknown fields included), a bad `binding_id` query, or a viewer-only signal kind | Fix the payload; do not retry unchanged |
| 400 | `invalid_nonce` | `time` | The `nonce` query parameter is missing or not 16 to 64 of `A-Z a-z 0-9 _ -` | Send a fresh random nonce |
| 400 | `event_not_declared` | `events` | The event type is not served by a declared capability | Declare the capability in `hello` |
| 400 | `observed_in_future` | `status`, `events`, `access/offline-decisions` | `observed_at` / `decided_at` is more than five minutes ahead | Fix the clock |
| 400 | `invalid_range` | `usage` | `ended_at` before `started_at` | Fix the record |
| 400 | `binding_required` | `events` (`detection.reported`) | A detection must name its `binding_id` | Add it |
| 400 | `invalid_artifact` | `events` (`detection.reported`) | `artifact_id` is not an artifact of that binding | Upload the frame first, then send its id |
| 400 | `content_type_not_allowed` | `artifacts`, `kiosk/.../evidence`, `media/{watch}/recording` | The content type is not allowed for that artifact kind, for evidence photos, or is not `video/webm` / `video/mp4` for a recording | Send an allowed type |
| 400 | `evidence_not_uploaded`, `checkout_refused`, `return_refused` | kiosk issue/return | The self-checkout workflow refused (photo missing, tool not eligible, remark missing...) | Show `detail`; start again |
| 400 | (detail only) | `jobs/{id}/progress`, `jobs/{id}/report` | The job's request or machine is no longer in progress / assigned | Stop the job; staff decide |
| 401 | (detail only) | all | Missing, malformed, stale, replayed or invalid signature | Re-sign with a fresh nonce and timestamp |
| 403 | (detail only) | all | Device revoked, key rotated, wrong device kind or tenant unavailable; a recording upload for a watch opened without `record` | Stop and ask staff |
| 403 | `requester_blocked` | kiosk issue | The member is restricted | Show `detail` |
| 404 | (empty) | all | `machines.integrations` (or the capability's child switch) is off; the id is not this adapter's own binding, command, job, watch or artifact; the binding does not serve the route's capability; another tenant's id; a kiosk session that expired | Treat as "not available" |
| 404 | `binding_unknown` | `events` | The event names a binding that is not this adapter's, or that does not serve the event's capability | Re-read `GET bindings` |
| 404 | `invalid_link` | `artifacts` | `service_request_id` is not a job in this space assigned to the binding's machine | Drop the link |
| 409 | `lease_mismatch` | `commands/{id}/ack` | The lease token does not own the command, or the device key was rotated after the lease (the command is closed) | Lease again |
| 409 | `unsupported_target` | `sessions/start` | Sessions need a machine binding | Bind a machine |
| 409 | `session_closed` | `sessions/{id}/stop` | The session already stopped | Nothing to do |
| 409 | `job_not_acknowledged` | `jobs/{id}/report` | The job was never acknowledged | Ack first |
| 400 | `unknown_consumable_key` | `jobs/{id}/report` | A `profile_consumptions` key is not an active consumable of the job's machine type in this space | Report only keys the type's profile lists |
| 400 | `consumable_recorder_not_allowed` | `jobs/{id}/report` | The type's profile does not let an adapter record that consumable | Leave it to staff |
| 400 | `invalid_profile_consumption` | `jobs/{id}/report` | A quantity is not positive, a whole-unit quantity (sheet, piece, use) is fractional, or an attribute is not one of the offered choices | Fix the measurement |
| 409 | `consumable_already_recorded` | `jobs/{id}/report` | That consumable already has a different recorded amount for this job (an identical repeat is a no-op) | Never replay a changed report |
| 409 | `job_not_active` | `jobs/{id}/file` | Files are served only for a live, acknowledged job | Lease again |
| 400 | `external_job_id_reserved` | `jobs/{id}/ack` | The vendor job id starts with `pending-`, the prefix SpaceWorks uses for a job not yet acknowledged | Send the vendor's real job id |
| 409 | `external_job_in_use`, `external_job_mismatch` | `jobs/{id}/ack` | The vendor job id is already used, or the job is bound to another one | Use one id per job |
| 409 | (detail only) | `jobs/{id}/ack`, `progress`, `report` | Printer-path conflicts: wrong external id, a different terminal report for the same job, an operation id reused | Never replay a changed report |
| 409 | `upload_missing` | `artifacts/{id}/complete` | The bytes have not been uploaded yet | Upload, then complete |
| 409 | `log_bundle_not_requested` | `artifacts` (`log_bundle`) | No open log-bundle command matches `command_id` | Upload only for a leased `diagnostics.log_bundle` |
| 409 | `audio_recording_not_consented` | `artifacts` (`audio_recording`) | No live watch with audio recording acknowledged | Record only during such a watch |
| 409 | `cache_too_large` | `access/cache` | More than 5000 credentials for one binding | Split the binding |
| 409 | `watch_ended` | media | The watch session has ended | Stop streaming |
| 409 | `tool_state_conflict`, `deposit_required` | kiosk issue/return | The tool changed state, or a deposit is needed first | Show `detail` |
| 409 | `<limit>_quota_reached` | `artifacts` | `adapter_artifacts_quota_reached` or `adapter_media_bytes_quota_reached` | Ask staff |
| 410 | `lease_expired` | `commands/{id}/ack` | The lease ran out before the ack (the command is requeued while its TTL lasts), or the command's TTL passed (it is closed `expired` and never leased again). A lease never runs past the command's TTL. The refused ack is audited | Lease again; never act on a command after `lease_expires_at` |
| 410 | `artifact_expired` | `artifacts/{id}/complete` | The artifact was purged (abandoned or over size) | Start a new upload |
| 413 | `artifact_too_large` | `artifacts`, `artifacts/{id}/complete`, `kiosk/.../evidence` | Over the kind's size cap (declared or uploaded) | Upload a smaller file |
| 413 | `frame_too_large` | `media/{watch}/snapshot` | The still is over the frame cap | Send a smaller JPEG |
| 423 | (detail only) | all | Tenant frozen for migration | Retry later |
| 429 | `rate_limited` | `events` (`detection.reported`) | Over 30 detections per binding per ten minutes | Slow down |
| 503 | `storage_unavailable` | artifacts, kiosk evidence, job files, recording | Object storage is unavailable | Retry with backoff |

Access decisions are **not** errors: `POST access/authorize`, `POST sessions/start` and `POST kiosk/sessions` answer
`200` (`201` for the kiosk) with `allowed: false` and a `reason` (see [api.md](api.md)); the adapter keeps its relay
off. A queued command whose capability's child switch was turned off before it was leased is never delivered: it
fails with `result_code: capability_switched_off` (a door `unlock` queued before `.access` went off does not run).

## Staff routes (`/api/v1/admin/`)

Staff routes add `403` (missing MANAGE_DEVICES or outside the machine scope) and:
`400 capability_target_mismatch`, `400 command_unknown`, `400 invalid_pin` (a new PIN is 6 to 12 digits),
`400 weak_pin` (one repeated digit, a straight run or a well-known PIN), `400 config_secret_refused`,
`400 webhook_url_refused`, `409 binding_exists`, `409 adapter_revoked`, `409 capability_not_declared`,
`409 pose_not_calibrated`, `409 watch_ended`, `409 credential_in_use`, `409 adapter_unavailable`, `409 job_exists`,
`409 audio_notice_required`, `409 capability_missing`, `413 config_too_large`, `429 too_many_presses`, plus the limit
refusals `adapter_bridges_quota_reached`, `adapter_watch_streams_quota_reached` and `adapter_snapshots_quota_reached`.
Shelf-pointer staff routes add `400 invalid_pose` (an unknown pose `kind`, or one that fails its schema),
`400 invalid_location` (a shelf check naming a location that is not this space's, or one twice) and
`400 too_many_targets` (more than 200 targets in one coverage question); see
[the shelf pointer](hardware/shelf-pointer.md).
