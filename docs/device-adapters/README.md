---
title: Device Adapter API v1
group: Reference
order: 60
summary: One vendor-neutral contract for bridges that connect machines, shelf pointers, scanners, doors and sensors to SpaceWorks.
---

# Device Adapter API v1

An **adapter** is an enrolled, signed device (see [Device protocol v1](../device-protocol.md)) that acts as a
bridge, like a Fabman bridge: it sits next to the hardware, calls out to SpaceWorks, and manages many
**targets** through explicit **bindings**. Vendor adapters (Bambu, Prusa, OctoPrint, Klipper, laser and
CNC controllers, shelf pointers, door controllers) live in their own repositories and speak only this
contract. SpaceWorks stays the system of record: an adapter is never a user and never an audit actor.

Status: built and shipped in 0.12.0 are the capability registry, JSON Schemas, models, signed routes, staff routes,
access, sessions, usage, controls, job dispatch and file fetch, shelf-pointer calibration, credentials, the kiosk, label
delivery, camera watch with the WebRTC signaling relay, audio, artifacts, detections, telemetry history, diagnostics, the
offline access cache, remote config, time sync and event notifications. **SpaceWorks core does not automate.** It stores,
shows and notifies; rules such as pausing a print on a detected failure belong to the adapter. The staff screen is
described in [Manage device adapters](../how-to/adapter-console.md). Read next: [authentication](authentication.md), [API reference](api.md),
[errors](errors.md), [versioning](versioning.md), [sequence diagrams](sequences.md) and
[build an adapter](build-an-adapter.md).

## Route family

Adapter routes live in the existing signed device family: `/api/v1/device/adapter/v1/...`. That reuses
signed authentication, replay protection, revocation, the default-deny route registry and the
`devices.E001` startup check. Every existing `/api/v1/device/` route keeps working unchanged. Staff
routes live under `/api/v1/admin/` and need `MANAGE_DEVICES` (plus machine scope for machine targets).
The whole family answers 404 unless `machines.integrations` is on for the space (default off).

## Targets and bindings

A binding joins one adapter to one target of type `machine`, `machine_type`, `storage_location`, `item`,
`box`, `door` or `space`, with the subset of declared capabilities used there. Storage locations, items
and boxes are staff data: they never appear on a public surface and a pose or location handle is never
sent anywhere but to the bound adapter.

## Capabilities

Each capability is one module under `backend/apps/devices/adapters/caps/` with its JSON Schemas; the
registry (`adapters/registry.py`) lists them. The adapter declares what it implements in `hello`.

| Capability | Direction | Purpose |
|---|---|---|
| `status`, `telemetry` | adapter to server | Normalised state (`idle`, `preparing`, `running`, `paused`, `finished`, `failed`, `error`, `offline`, `maintenance`), progress, ETA, typed error codes, numeric readings |
| `events` | adapter to server | Typed, append-only events, idempotent by `operation_id` |
| `job.dispatch`, `file.fetch` | both | Lease, ack, progress, terminal report with measured consumption; signed artifact URL; applied through the machine-service workflow |
| `control` | server to adapter | `pause`, `resume`, `cancel`, `power` by command lease/ack/result, staff-initiated and audited |
| `access.authorize`, `door.access` | request/response | Card QR, NFC or PIN; the server decides with the existing permission, supervision, induction and session rules and answers allow or deny with a typed reason, session id and time limit |
| `session.start`, `session.stop`, `usage.log` | adapter to server | Metered sessions through the machine-session service; one immutable usage record per session or job |
| `consumables` | adapter to server | Material levels and runout events |
| `safety` | server-enforced | Idle auto-off, area-clear confirmation, max session length, from per-type or per-machine config |
| `maintenance.report` | adapter to server | A fault goes to the maintenance workflow |
| `locate.indicate` | server to adapter | Point at or light a storage location, item or box. Staff only |
| `locate.calibrate` | both | Calibration session, saved opaque poses per location, bulk walk-the-shelves |
| `label.print` | server to adapter | Maps onto the existing label commands |
| `scan.report`, `sensor.report` | adapter to server | Scans and sensor readings or alarms |
| `media.snapshot`, `media.stream` | both | Camera only while someone watches: WebRTC signaling relayed by the server, snapshot fallback, no recording by default |
| `checkout.kiosk` | both | Public self-checkout and return at a device. The adapter never bypasses a step: member authenticates, scans the tool, uploads evidence through the presigned staging flow, and the same self-checkout workflow issues or returns |

## Media and data capabilities

See [media-and-data.md](media-and-data.md): audio, talk, artifacts, detections, telemetry history, diagnostics,
offline access cache, remote config and time sync (decision 321).

## JSON Schemas

Every command, event and payload has a schema in [`schemas/`](schemas/). They are generated from the
registry by `scripts/export_adapter_schemas.py`, and the server validates with the same dictionaries, so
the files cannot drift from the code. A test pins that.

## Adding a capability

1. Add `backend/apps/devices/adapters/caps/<name>.py` with a `CAPABILITY` and its schemas.
2. List it in `registry.py`.
3. Run `python scripts/export_adapter_schemas.py` and commit the schemas.
4. Add a conformance test and mock-adapter coverage.

## Security

The adapter authenticates with its own Ed25519 key; there is no bearer token. Payloads are bounded and
unknown fields are refused. The adapter receives no requester identity beyond what a decision needs, never
sends money, and every effect runs through the workflow that owns it, so audit rows have the real staff
actor or none, with device provenance in metadata.
