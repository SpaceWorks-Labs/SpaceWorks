# Machine integrations

This page describes the server side of connecting machines to SpaceWorks: how a device proves who it
is, which routes it may call, what it may change, and what is not built. The wire formats live in
three sibling documents, and this page links to them rather than repeating them:

- [Device protocol v1](../device-protocol.md): enrollment, signed requests, rotation, revocation and
  test vectors.
- [Printer delivery and measured reports](../device-printer-protocol.md): printer bindings, command
  lease/ack, telemetry, terminal results, and the machine-integration routes (queue pull, job
  reports, heartbeat status snapshot).
- [Label commands](../device-label-commands.md): sending QR print batches to a label printer.

## 1. What the integration layer is

It is the `devices` app (`backend/apps/devices/`, module `devices`) plus one capability,
`machines.integrations`. A device is an enrolled piece of hardware with its own Ed25519 key. It is
not a user account, holds no role, and is never an audit actor.

It is not a printer agent. No agent program, no vendor adapter and no fleet scheduler ships in this
repository. The machine-integration routes are a foundation: the endpoints and data a future agent
would call, off by default. SpaceWorks stays the system of record; every change to a machine-service
request still goes through the machine-service workflow.

## 2. Data model

All models live in `backend/apps/devices/` and are re-exported from `models.py`.

| Model | File | Purpose and key fields |
|---|---|---|
| `Device` | `models_identity.py` | `kind` (`printer`, `label_printer`, `generic`), `status` (`pending`, `active`, `revoked`), `public_key`, `key_fingerprint` (unique across the deployment), monotonic `key_version`, `last_seen_at`, `offline_threshold_seconds` (default 300), `offline_since`. |
| `DeviceEnrollment` | `models_identity.py` | One-time enrollment: `purpose` (`enroll`, `rotate`, `reactivate`), `token_digest`, `challenge_digest`, `expires_at`, `used_at`, `revoked_at`. Only SHA-256 digests are stored. |
| `DeviceRequestNonce` | `models_identity.py` | Replay record, unique on `(device, key_version, nonce_digest)`. |
| `DeviceEvent` | `models_events.py` | Append-only device provenance with source-local `*_snapshot` columns. |
| `DeviceCommand` | `models_commands.py` | Delivery ownership: `status`, `attempts`, `lease_token_digest`, `lease_expires_at`, pinned `device_key_version`. |
| `PrinterDeviceBinding` | `models_printers.py` | One printer device to one `machines.Machine`; `enabled` (default true), `auto_apply_terminal` (default false). |
| `PrinterJob`, `PrinterJobConsumption` | `models_printers.py` | One run on a machine-service request and its immutable terminal report and consumptions. |
| `LabelPrintCommand`, `LabelPrintResult` | `models_labels.py` | Label delivery history and immutable per-operation receipts. |
| `MachineTypeIntegration` | `models_integrations.py` | Binds an integration `kind` to one `machines.MachineType` in one makerspace. Only `printer_agent` exists. `enabled` defaults to false; `config_schema_version` is 1. Unique per `(makerspace, machine_type, kind)`. |
| `PrinterStatusSnapshot` | `models_integrations.py` | The latest bounded status a printer sent on its heartbeat. One row per device (the device is the primary key), overwritten in place. |

Tenancy: every model carries a `makerspace` foreign key, except `DeviceRequestNonce` and
`PrinterJobConsumption`, which hang off a device or a job. Every service filters by the makerspace
of the authenticated device or of the staff actor's scope.

Append-only and immutable rows:

- `DeviceEvent` refuses update and delete in the ORM and through the `devices_event_append_only`
  trigger (migration `0001`).
- `LabelPrintResult` refuses update and delete in the ORM, and a database guard freezes claimed
  label commands (`migrations/_label_guards.py`).
- A claimed `PrinterJob` report is immutable: a database guard (`migrations/_printer_claim_guards.py`)
  freezes claimed identities, measurements and consumptions.
- Audit rows go through `apps.audit.services.record` and are append-only like every audit row.

`MachineTypeIntegration` is mutable configuration. `PrinterStatusSnapshot` is overwritten on each
stored snapshot and keeps no history.

## 3. The device protocol

### Authentication

1. A staff member with `MANAGE_DEVICES` creates a device, which returns a one-time enrollment token
   (TTL `DEVICE_ENROLLMENT_TTL_SECONDS`, default 900). Issuing a new enrollment revokes any open one.
2. The device generates its own Ed25519 key, asks for a challenge, signs the enrollment message and
   completes enrollment. Completion activates the device and increments `key_version`.
3. Every later call is signed: `X-Device-Id`, `X-Device-Key-Version`, `X-Device-Signature-Version: v1`,
   `X-Device-Timestamp`, `X-Device-Nonce`, `X-Device-Signature`. The signature covers the method, the
   exact raw request target, the timestamp, the nonce and the SHA-256 of the body.
4. The server accepts a timestamp within `DEVICE_SIGNATURE_MAX_SKEW_SECONDS` (default 300) and claims
   each nonce once per key for `DEVICE_NONCE_TTL_SECONDS` (default 86400). The nonce is inserted only
   after the signature verifies.

Rotation is a new staff-issued enrollment for an active device, completed with a new key; old
signatures stop working when `key_version` advances. Revocation (`POST .../revoke`) blocks the device
at once; only a `reactivate` enrollment brings it back. There is no shared bearer token for agents.
Full detail and test vectors: [device-protocol.md](../device-protocol.md).

### Device routes

Every route under `/api/v1/device/` must appear in `route_registry.DEVICE_ROUTES`, keyed by
(qualified URL name, method), with an auth mode, the device kinds allowed and the modules required.
`DeviceRoutePermission` denies anything unlisted. The system check `devices.E001` refuses startup
when the registry and the URLconf disagree.

| Method and path | Kinds | Purpose |
|---|---|---|
| `POST /api/v1/device/enrollments/{id}/challenge` | all | Get a challenge for a candidate key (enrollment token, not signed). |
| `POST /api/v1/device/enrollments/{id}/complete` | all | Prove possession and activate or rotate (enrollment token). |
| `POST /api/v1/device/heartbeat` | all | Record activity and recover an offline device; optional `status_snapshot`. |
| `POST /api/v1/device/commands/lease` | all | Lease the next queued command, or `{"command": null}`. |
| `POST /api/v1/device/commands/{id}/ack` | all | Acknowledge a leased command. |
| `POST /api/v1/device/printer-jobs/{id}/telemetry` | `printer` | Advisory progress for an acknowledged job. |
| `POST /api/v1/device/printer-jobs/{id}/result` | `printer` | Immutable terminal report (completed or failed). |
| `GET /api/v1/device/label-commands/{id}/content` | `label_printer` | Download the label ZIP after acknowledging. |
| `POST /api/v1/device/label-commands/{id}/result` | `label_printer` | Report a label print outcome. |
| `GET /api/v1/device/integrations/queue` | `printer` | Pull approved jobs for the bound machine's type. |
| `POST /api/v1/device/integrations/jobs/{service_request_id}/report` | `printer` | Report a job `started`, `completed` or `failed`. |

Module requirements: the base routes need `devices`; printer routes need `devices`, `machines` and
`machine_service`; label routes need `devices` and `qr_print_batches`. The two integration routes
have an empty module tuple in `route_registry_r2.py` on purpose: the view answers 404 for the whole
`machines.integrations` chain instead.

### Staff routes

| Method and path | Requires | Purpose |
|---|---|---|
| `GET, POST /api/v1/admin/makerspace/{id}/devices` | `MANAGE_DEVICES`, `devices` | List devices; create a pending device and its first enrollment. |
| `GET, PATCH /api/v1/admin/devices/{id}` | same | Read; change only `name` and `offline_threshold_seconds`. |
| `POST /api/v1/admin/devices/{id}/enrollments` | same | New enrollment (enroll, rotate or reactivate by status). |
| `POST /api/v1/admin/devices/{id}/revoke` | same | Revoke immediately. |
| `GET, POST /api/v1/admin/makerspace/{id}/device-printer-bindings` | `MANAGE_DEVICES` + machine scope, three modules | List and create printer bindings. |
| `PATCH, DELETE /api/v1/admin/device-printer-bindings/{id}` | same | Change `enabled`/`auto_apply_terminal`, or remove. |
| `GET, POST /api/v1/admin/makerspace/{id}/printer-jobs` | same | List printer jobs; create one for an in-progress request. |
| `GET /api/v1/admin/printer-jobs/{id}` | same | Job detail. |
| `POST /api/v1/admin/printer-jobs/{id}/apply` | same | Apply a held report through the workflow. |
| `GET, POST /api/v1/admin/qr-print-batches/{id}/label-commands` | `MANAGE_QR`, `devices`, `qr_print_batches` | Label send history; send a batch. |
| `GET, POST /api/v1/admin/makerspace/{id}/machine-types/{type_id}/integrations` | `MANAGE_DEVICES` + type scope, `machines.integrations` | List or create integration bindings (created disabled). |
| `GET, PATCH, DELETE /api/v1/admin/machine-type-integrations/{id}` | same | Read; change `enabled`/`config_schema_version`; remove. |
| `GET /api/v1/admin/makerspace/{id}/machine-types/{type_id}/integration-status` | same | Read-only: enabled printer bindings on machines of the type, last seen, latest snapshot. |

Every route above has an `extend_schema` entry; the device routes are tagged `Device protocol` and the
staff routes `Devices`. `openapi.py` registers the `DeviceSignature` security scheme. Swagger UI is at
`/docs/`.

### Limits

There is no DRF throttle on the device routes. The bounds are in the protocol and services:

- Replay: one nonce per key, timestamps within the skew window.
- Status snapshot: a snapshot within 5 seconds of the last stored one is dropped (`throttled`); one
  not newer than the stored `observed_at` is ignored (`stale`); one more than 5 minutes in the future
  is refused.
- Queue pull: at most 50 jobs per response.
- Command delivery: lease `DEVICE_COMMAND_LEASE_SECONDS` (default 60), at most
  `DEVICE_COMMAND_MAX_ATTEMPTS` (default 10) attempts.

### Error shapes

- Signature failures: `401` with `WWW-Authenticate: SpaceWorks-Device-v1` and `{"detail": "..."}`.
  A revoked or rotated key, a stale `key_version`, a replay and a tampered body look the same.
- Module disabled: `400` with `{"module": "<key> is disabled for this makerspace."}`.
- Payload errors: `400` with field-keyed messages. Device payload serializers refuse unknown fields.
- Integration conflicts: `409` with `{"detail": "...", "code": "..."}`, where `code` is one of
  `job_unknown`, `job_conflict`, `job_not_started`, `job_not_reported_started` or `integration_exists`.
- Integration off or target out of scope: `404`. A signed request from a makerspace where the
  `devices` module itself is off fails earlier, during authentication, with the `400` above.
- Tenant frozen for migration: `423`. Expired delivery lease: `410`. Enrollment used or expired: `410`.

## 4. The printer-fleet agent

What exists on the server today:

- An agent would be an ordinary enrolled `printer` device speaking protocol v1.
- It reaches the integration routes only when all of these hold: the makerspace has
  `machines.integrations` (with `devices`, `machines` and `machine_service` on); the device is active;
  its enabled `PrinterDeviceBinding` names an active machine; and that machine's type has an enabled
  `MachineTypeIntegration` of kind `printer_agent`. `integration_access.device_binding` resolves this
  chain on every call. Otherwise the route answers 404.
- `printer_agent` binds only the built-in 3D printer type (`machines.printer_capabilities.is_printer_type`).

What an agent is expected to do, using only these routes:

1. Enroll once and keep its private key and `key_version`.
2. Send heartbeats, optionally with a `status_snapshot` (state, progress, layers, temperatures, up to
   16 spools, a `clear_token`). Numbers are clamped to fixed ranges. The response says `stored`,
   `stale`, `throttled` or `not_integrated`.
3. Pull the queue. It lists requests accepted for the machine's type (or the machine's legacy bucket)
   and the request in progress on that machine, oldest accepted first. Each job carries only ids,
   status, estimates and timestamps: no requester, title, file or storage location.
4. After staff start a request on its machine, report `started` with its own `external_job_id`. The
   device cannot start a request itself; starting picks the material pool, which is a staff decision.
5. Report `completed` or `failed` with a stable `operation_id`, `actual_minutes` and explicit
   `consumptions`. Retries reuse the same `operation_id` with a fresh nonce.

A failure is always held for staff review (`needs_review`). A completion is held too unless the
binding's `auto_apply_terminal` is on. Staff apply a held report with `POST .../printer-jobs/{id}/apply`.

The older command path from phase 7b also works for printers: staff create a printer job, the device
leases and acknowledges the command, then sends telemetry and a result.

Not shipped: an agent program, any vendor adapter, fleet sync or scheduling, live printer controls,
camera, file or G-code transfer, and a console screen for integrations. The capability is
`frontend_exposed=False`, so it can be turned on only in `/control/`. No scheduled task exists for it.

## 5. Adding a device kind or integration kind

These are the registries the existing code composes. Follow the established pattern of a dated or
lane-named sibling file (`*_7b.py`, `*_7c.py`, `*_r2_l10.py`) imported by the main catalogue.

1. **Model choices.** Add the value to `Device.Kind` or `MachineTypeIntegration.Kind` and write a
   migration chained off the actual leaf in `backend/apps/devices/migrations/`.
2. **Route registry.** Add each new device route to a `route_registry_*.py` sibling, merged into
   `DEVICE_ROUTES`. Name the kinds and the modules it needs. Update `ALL_KINDS` in
   `route_registry.py`, which is a literal set. Device views must use exactly `DeviceAuthentication`
   and `DeviceRoutePermission` (subclass `SignedDeviceView`), or `devices.E001` fails.
3. **URLs.** Add a `urls_*.py` sibling under the `devices` namespace and append it in `urls.py`. Object
   routes use a `pk` kwarg, because the origin-scope resolver reads only `kwargs["pk"]`.
4. **Integration access.** `integration_access.device_binding` and
   `services_integration_bindings.create_integration` currently accept only printers and the
   `printer_agent` kind. A new kind needs its own type check and chain there.
5. **Staff authorization.** Check `rbac.can(actor, Action.MANAGE_DEVICES, makerspace_id)` and scope
   lists with `rbac.scope_by_action`; check machine scope (`covers_type`, `can_manage_machine`).
   Classify new staff route names in the delegated route catalogue (the L10 ones are in
   `accounts/delegated_route_catalog_r2.py`) and add detail routes without a `makerspace_id` to an
   `origin_scope_routes_*.py` table in `makerspaces/`.
6. **Capability.** If the feature should be switchable, add a definition sibling in
   `makerspaces/capability_definitions_*.py` (see `capability_definitions_r2_l10.py`). A new module
   key also means editing `docs/MODULES.md`.
7. **Serializers.** Subclass `StrictSerializer` so unknown fields are refused, bound every size and
   number, and never accept money, files or credentials.
8. **Export and migration.** Classify every new model in `data_export` (exported fields, or
   `OMITTED_MODELS` with a reason, as in `classification_r2_l10.py`) and decide each `accounts.User`
   foreign key (`RELATIONAL_USER_FIELDS`, and `accounts/merge_registry_rows_accounts.py`). Add the field snapshot to
   a `tenant_migration/catalog_*.py` sibling. Exported models also need the reference, projection,
   unique-value and authority siblings that 7b added (`tenant_migration/*_7b.py`).
9. **Audit.** Add an entry for every new action to an `audit/presentation_catalog_*.py` sibling, and
   declare id fields in audit metadata in a `tenant_migration/audit_references_*.py` sibling.
10. **PII and purge.** Register free-text PII fields with the encryption registry (as
    `encryption/registry_7b.py` does for `PrinterJob.failure_reason`) and extend the devices purge
    collector (`makerspaces/module_purge_collectors_devices.py`).
11. **OpenAPI.** Give every view an `extend_schema` with request, response and error schemas, then
    regenerate `frontend/openapi-schema.json` and `frontend/src/generated/api.ts`.
12. **Tests.** The backend suite lives under `backend/tests/`, which is kept local and not published;
    run it with `./scripts/dev.sh test`.

## 6. Security model

- **Tenant scoping.** Authentication resolves the device through the servable-makerspace queryset and
  selects that one tenant before the source gate and the nonce claim; a device cannot name another
  tenant. Every device mutation takes `services_locks.lock_tenant` first (source gate, locked
  `devices` module check, servability re-check). Staff routes scope through `accounts.rbac` before
  object lookup, so an out-of-scope object is a 404. Tables with a makerspace foreign key are also
  covered by the generated Postgres RLS backstop in `apps/tenant_rls/`; application scoping stays
  the primary control.
- **RBAC.** `MANAGE_DEVICES` for device identity, printer bindings, printer jobs and integration
  bindings, plus machine or machine-type scope where a machine is involved. `MANAGE_QR` to send
  labels. `MANAGE_DEVICES` is a Space Manager default, is not held by Inventory or Machine Managers by
  default, and is never organization-grantable. A device principal never reaches `accounts.rbac`.
- **Credential storage.** The device public key is stored as public material; the private key never
  leaves the device. Enrollment tokens, challenges and command lease tokens are stored only as
  SHA-256 digests and shown once. Nonces are stored as digests. None of these travel in exports,
  tenant moves or restores; a restored or moved device returns to `pending` and must enroll again.
- **Switches and defaults.** The `devices` module is opt-in. `machines.integrations` is off by default.
  `MachineTypeIntegration.enabled` defaults to false. `auto_apply_terminal` defaults to false.
  Device offline/recovery notifications are off on every channel by default.
- **Audit.** Device-originated rows use `actor=None` with typed metadata. Actions include
  `devices.created|updated|enrollment_created|enrolled|rotation_started|rotated|revoked`,
  `devices.heartbeat_received|offline_detected|recovered|auth_artifacts_purged`, the printer and label
  `devices.*` actions, `devices.integration_bound|updated|unbound` (staff actor), and
  `machine_service.agent_report_applied|refused`.
- **What a device can never do.** It cannot move money or send a price: unknown fields are refused and
  charges come from the workflow's own cost seam at current pricing. It cannot change request state
  except through `service_workflow_actions.complete/fail`, and cannot start, accept or reject a
  request. Its status snapshot and telemetry never change `Machine.status`, a request, consumption or
  money. It never receives requester identity, request titles, files or storage locations from the
  queue. It is never an audit actor, evidence uploader or scan actor.

## 7. Deferred and not built

- A device agent, a Bambu or other vendor adapter, and fleet sync or scheduling.
- Live controls, camera, and the shelf pointer named in the capability text. Door and access-control
  hardware is listed as further work in `docs/future-work.md`.
- A staff console for integration bindings or the status list (`frontend_exposed=False`).
- Per-binding settings: a `MachineTypeIntegration` stores only `config_schema_version`, and only 1 is
  accepted.

One related piece is built and waits on an integrated machine. Metered machine sessions take a
`device` source: when `machines.sessions` is also on, an applied `started` report opens a `device`
session on the bound machine and `completed`/`failed` closes it with the reported minutes
(`machines/sessions_device.py`). It attributes the session to the job's member only when they are an
active member, otherwise holds it unattributed for staff. A device session that runs a job is billed
through the job only. There is no separate device route for sessions.

## 8. Where things live

| Path | Contents |
|---|---|
| `backend/apps/devices/models_*.py` | Identity, events, commands, printer, label and integration models. |
| `backend/apps/devices/protocol.py` | Canonical v1 bytes, encodings, `INTEGRATION_SCHEMA_VERSION`. |
| `backend/apps/devices/authentication.py`, `principal.py`, `permissions.py` | Signed-request authentication, `DevicePrincipal`, default-deny route permission. |
| `backend/apps/devices/route_registry*.py`, `checks.py` | Device route registry and its startup checks. |
| `backend/apps/devices/urls*.py` | URL composition (`urls_r2.py` holds the integration routes). |
| `backend/apps/devices/integration_access.py` | The 404 gate and the device to binding to machine to type chain. |
| `backend/apps/devices/services_integration_*.py` | Snapshot storage, queue and job reports, staff bindings and status. |
| `backend/apps/devices/views_heartbeat.py`, `views_integrations.py` | Heartbeat and integration views. |
| `backend/apps/devices/serializers_integrations.py` | Bounded, clamped integration payloads. |
| `backend/apps/makerspaces/capability_definitions_r2_l10.py` | The `machines.integrations` switch. |
| `backend/apps/machines/sessions_device.py` | Device-sourced machine sessions. |
| `docs/INVARIANTS.md` | The device identity, printer and machine-integration invariants. |
