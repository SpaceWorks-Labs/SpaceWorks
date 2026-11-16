---
title: Adapter sequence diagrams
group: Reference
order: 66
summary: The main adapter flows as sequence diagrams: enroll and hello, access and session, control, shelf-pointer calibration and indication, video watch, jobs and kiosk checkout.
---

# Sequence diagrams

## Enroll and hello

```mermaid
sequenceDiagram
  participant S as Staff (console)
  participant API as SpaceWorks
  participant A as Adapter
  S->>API: POST admin/makerspace/{id}/devices {kind: adapter}
  API-->>S: device + one-time enrollment token
  S->>A: token (out of band)
  A->>API: enrollment challenge / complete (Ed25519 proof)
  API-->>A: device active, key_version 1
  A->>API: POST hello {kind, capabilities}
  API-->>A: config_version, bindings (none yet)
  S->>API: POST admin/adapters/{id}/bindings {machine, capabilities}
  A->>API: GET bindings (or the next status response shows a new config_version)
  API-->>A: bindings
```

## Access and a metered session

```mermaid
sequenceDiagram
  participant M as Member
  participant A as Adapter (reader + relay)
  participant API as SpaceWorks
  M->>A: taps card / NFC / enters PIN
  A->>API: POST sessions/start {binding, credential}
  API->>API: credential -> member, session rules (machine access grant, check-in, booking, lockout, in use)
  alt allowed
    API-->>A: allowed, session_id, max_seconds
    A->>A: power relay on, enforce max_seconds
    A->>API: POST status (running)
    M->>A: done
    A->>API: POST sessions/{id}/stop {reason: member, minutes}
    API-->>A: stopped (usage entry + charge raised in the ledger)
  else denied
    API-->>A: allowed false + reason code
    A->>A: relay stays off (a denial never changes a running session)
  end
```

## Control (staff pauses a machine)

```mermaid
sequenceDiagram
  participant S as Staff
  participant API as SpaceWorks
  participant A as Adapter
  S->>API: POST admin/adapter-bindings/{id}/commands {control, pause}
  API->>API: RBAC + machine scope + schema check + audit (staff actor)
  A->>API: POST commands/lease
  API-->>A: command + lease token
  A->>A: pause the machine
  A->>API: POST commands/{id}/ack {succeeded}
  A->>API: POST status (paused)
```

## Shelf pointer: calibrate, then indicate

```mermaid
sequenceDiagram
  participant S as Staff
  participant API as SpaceWorks
  participant P as Pointer adapter
  Note over S,P: Calibrate one location (poses are staff-only, never public, never in a dump)
  S->>API: POST adapter-bindings/{id}/aim {pose}
  P->>API: lease aim, ack
  S->>API: POST adapter-bindings/{id}/jog {dx, dy}
  P->>API: lease jog, ack, event calibration.position {pose}
  S->>API: GET adapter-bindings/{id}/position
  S->>API: PUT adapter-bindings/{id}/poses {storage_location, "Shelf A", pose}
  Note over S,P: Indicate
  S->>API: POST adapter-bindings/{id}/indicate {point, Shelf A}
  API->>API: look up the saved pose, queue the command
  P->>API: lease indicate {mode, pose, duration}, ack
```

### Show on shelf, clear and shelf checks (staff)

```mermaid
sequenceDiagram
  participant S as Staff (item, box, issue line, stocktake)
  participant API as SpaceWorks
  participant P as Pointer adapter
  S->>API: POST makerspace/{id}/shelf-pointer/coverage {targets}
  API-->>S: {results: [{target, covered}]}  (never a pose; 404 while machines.integrations is off)
  S->>API: POST makerspace/{id}/shelf-pointer/show {target_type, target_id, duration_seconds}
  API->>API: find the covering pose, clamp to laser_max_power_pct / max_on_seconds, audit (no pose)
  P->>API: POST commands/lease  (indicate {mode, pose, duration_seconds})
  P->>API: POST commands/{id}/ack
  S->>API: POST makerspace/{id}/shelf-pointer/clear
  API->>API: always queued: never capped or rate limited
  P->>P: switches off; also auto-clears when duration_seconds ends
  S->>API: GET makerspace/{id}/shelf-pointer/locations, then POST makerspace/{id}/shelf-checks {entries}
```

Pose kinds (`pan_tilt`, `led_segment`, `galvo_xy`) are published in `schemas/pose.*.json`; see the
[shelf-pointer hardware page](hardware/shelf-pointer.md) for what a Raspberry Pi or ESP32 adapter must do.

## Camera watch (staff or the job owner; recording opt-in)

```mermaid
sequenceDiagram
  participant V as Viewer (staff or job owner)
  participant API as SpaceWorks
  participant A as Adapter (camera)
  V->>API: POST adapter-bindings/{id}/watch {record?}  or  POST member/adapter-watch/requests/{id}
  API->>API: switch + limit check, audit row naming the viewer, 5 minute session
  V->>API: POST member/adapter-watch/{id}/signal {offer}
  A->>API: GET media/{watch}/signal?after=0  (offer + optional TURN ice_servers)
  A->>API: POST media/{watch}/signal {answer, candidates}
  V->>API: GET member/adapter-watch/{id}/signal  (answer, candidates)
  Note over V,A: media flows peer to peer; the server only relays signaling
  A->>API: POST media/{watch}/snapshot  (fallback still, cached 60 s, only while watching)
  V->>API: GET member/adapter-watch/{id}/frame
  V->>API: DELETE member/adapter-watch/{id}
```

Only the watch's own viewer (staff with MANAGE_DEVICES and machine scope, or the member whose in-progress request runs on
that machine) can use the signaling, frame and end routes; anyone else gets 404. Recording needs
`machines.integrations.recording`, is requested per watch, uploaded by the adapter through
`POST media/{watch}/recording` (a presigned upload), deleted after seven days by a Celery sweep, and audited at every
step. TURN is optional: set `ADAPTER_TURN_URLS` and `ADAPTER_TURN_SECRET` and both sides receive ephemeral credentials.

## Job dispatch and files (`job.dispatch`, `file.fetch`)

```mermaid
sequenceDiagram
  participant S as Staff
  participant API as SpaceWorks
  participant A as Adapter
  S->>API: POST adapter-bindings/{id}/jobs {service_request_id}
  API->>API: in-progress request assigned to the bound machine; PrinterJob + adapter_job command; audit
  A->>API: POST jobs/lease
  Note over API: held back while the area-clear gate (binding config) is not satisfied
  A->>API: POST jobs/{id}/ack {lease_token, external_job_id}
  A->>API: GET jobs/{id}/file  (short-lived signed URLs, audited)
  A->>API: POST jobs/{id}/progress {progress_percent}
  A->>API: POST jobs/{id}/report {operation_id, outcome, actual_minutes, consumptions[], profile_consumptions[]?}
  API->>API: claim (idempotent by operation_id) then staff review; machine-service workflow complete or fail
```

The run record is the existing printer job, so the legacy printer routes are untouched. An adapter binding never
auto-applies a terminal report: it lands in `needs_review` and staff approve it through the existing printer-job
approve route, which calls the same `complete` or `fail` workflow actions.

## Kiosk checkout (`checkout.kiosk`, child switch `machines.integrations.kiosk`)

```mermaid
sequenceDiagram
  participant M as Member
  participant A as Adapter (kiosk)
  participant API as SpaceWorks
  M->>A: NFC tag, member number + PIN, or card QR + PIN
  A->>API: POST kiosk/sessions {binding_id, credential}
  API->>API: member lookup + lockout, audit; 5 minute session bound to this device and key
  A->>API: POST kiosk/sessions/{sid}/scan {qr_payload}  (checkout | return | ineligible)
  A->>API: POST kiosk/sessions/{sid}/evidence {evidence_type, content_type}  (presigned STAGING upload)
  A->>A: PUT the photo to upload_url
  A->>API: POST kiosk/sessions/{sid}/issue {qr_payload, evidence_id}
  A->>API: POST kiosk/sessions/{sid}/return {qr_payload, evidence_id, remark}
  A->>API: DELETE kiosk/sessions/{sid}
```

Issue and return are the existing self-checkout workflow, unchanged: authenticated member, eligible tool, uploaded
issue evidence, return photo AND remark, same-requester return, borrow limits, charges and audit. The adapter cannot
skip any of it; refusals come back as typed codes (`tool_state_conflict`, `requester_blocked`, `deposit_required`,
`evidence_not_uploaded`, `checkout_refused`, `return_refused`).

## Label printing (`label.print`)

Staff send a QR label batch to the adapter's device exactly as to a label printer. The adapter hears about it as an
adapter command `label.print` / `print` carrying `label_command_id`, then leases the command, downloads the content
and reports the result through the existing label routes.
