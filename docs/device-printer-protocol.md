# Printer delivery and measured terminal reports

Phase 7b uses the [device signature protocol](device-protocol.md). A Device holds no staff role.
Every device request uses a fresh signed nonce, including retries of an identical report. The stable
terminal operation UUID is a separate identity used to prevent duplicate workflow effects.

Staff hold `MANAGE_DEVICES` and current management scope for the selected Machine. The adapter
requires all three modules: `devices`, `machines`, `machine_service`. Disabled modules answer 400;
a tombstoned devices app has no routes and answers 404.

## Bind and create

`POST /api/v1/admin/makerspace/{makerspace_id}/device-printer-bindings`:

```json
{"device_id":"<enrolled-printer-uuid>","machine_id":123,"enabled":true,"auto_apply_terminal":false}
```

The device and machine must be active and belong to that makerspace. Binding policy is updated with
`PATCH /api/v1/admin/device-printer-bindings/{id}` (only `enabled` and `auto_apply_terminal`). DELETE
removes the binding. Disabling or deleting it cancels unprocessed commands and preserves job history.

`POST /api/v1/admin/makerspace/{makerspace_id}/printer-jobs`:

```json
{"binding_id":"<binding-uuid>","service_request_id":456,"external_job_id":"agent-job-123"}
```

The request must already be in progress and assigned to the exact bound machine. External identity
is immutable, unique per device, and never inferred from a filename or request title.

Both staff collections support paginated GET. Job detail is
`GET /api/v1/admin/printer-jobs/{id}`. Swagger documents request, response and refusal schemas.

## Delivery ownership

`POST /api/v1/device/commands/lease` with `{}` returns `{"command":null}` or a command containing
`command_id`, `kind`, `lease_token`, `lease_expires_at`, `printer_job_id`, `external_job_id` and
`service_request_id`. Only the exact active owning device can receive it. The token is returned once;
its SHA-256 digest is stored, omitted from exports and never returned to staff.

`POST /api/v1/device/commands/{command_id}/ack` with `{"lease_token":"<returned-token>"}` acknowledges
ownership. Identical acknowledgement is cached success. A wrong or replaced token conflicts with 409;
expired unacknowledged delivery answers 410 after committing requeue/backoff. Delivery leases default
to 60 seconds and at most 10 attempts. Expiry is processed lazily when polling/acknowledging.

Acknowledgement survives a long print. Later telemetry/results require the owning device signature
and acknowledged command; they do not need an unexpired delivery lease. Rotation or revocation
invalidates prior command ownership. Agents must keep a durable local mapping from the server job ID
to their actual print; transport delivery may happen more than once.

## Telemetry and terminal result

`POST /api/v1/device/printer-jobs/{id}/telemetry`:

```json
{"external_job_id":"agent-job-123","telemetry_state":"running","progress_percent":25}
```

State is `idle`, `running` or `paused`. This only updates advisory job fields and device last-seen.
It does not change `Machine.status`, the public response, consumption or money.

`POST /api/v1/device/printer-jobs/{id}/result` for completion:

```json
{
  "operation_id":"<stable-operation-uuid>",
  "external_job_id":"agent-job-123",
  "outcome":"completed",
  "actual_minutes":42,
  "consumptions":[{"machine_consumable_id":789,"quantity":"2.50"}],
  "actual_grams":"12.00"
}
```

`consumptions` is required, including an explicit empty list. These are existing `MachineConsumable`
inputs belonging to the assigned machine. Count inputs must be whole. `actual_grams` is only for an
existing reserved weight pool. A non-weight reservation instead requires `actual_quantity`, matching
its unit. Omit both when no pool is reserved; never send both. All measurements must be finite and
nonnegative (individual consumption quantities must be positive).

Failure uses `outcome:"failed"` and additionally requires nonblank `failure_reason` (maximum 1000
characters) and `percent_complete` (0–100). It accepts the same metering inputs and creates no payment.
Completion cannot include failure fields. Unknown fields, including price/amount/currency/payment
status, are refused. Charges are calculated by the existing workflow using current tenant pricing.

The server commits the immutable report before attempting workflow effects. Retrying the same
operation and canonical payload returns the stored job; changing either conflicts with 409. Keep the
operation UUID stable across transport retries, and use a fresh signature nonce each time.

Automatic application is opt-in per binding. By default a report becomes `needs_review` and leaves the
request running. Scoped staff apply it with
`POST /api/v1/admin/printer-jobs/{id}/apply` and `{}`. Application and its provenance commit together.
A workflow or applied-provenance failure rolls back all effects and records review in a new transaction;
review is never retried automatically. Admission failures remain typed refusals.

## Movement and retention

Tenant moves preserve typed reports and source snapshots, disable bindings, cancel commands, remove
lease authority and reset devices to pending. Applied history stays applied; unprocessed work becomes
inert review. Re-enrollment does not revive imported work. Device purge removes the printer ledger;
machine-adapter purge nulls live targets while retaining device history. Missing targets cannot deliver
or apply. Free-text printer failure notes use scoped encryption; adapter audit metadata contains only
typed identifiers and outcomes. The existing workflow's reason fields retain their existing storage
contract.

## Machine integrations (release 2; integration schema 1; foundation only)

The integration itself (an on-device agent, a vendor adapter, fleet scheduling, live controls,
camera, shelf pointer) is **deferred** (owner decision #76). These routes are the server side a future
agent would use. They are **off by default**: unless the makerspace has the `machines.integrations`
capability (which needs `devices`, `machines` and `machine_service`), every route below answers
**404** to staff and to devices. One exception: when the `devices` module itself is off, a signed device
request fails earlier, at authentication, with 400 `{"module": ...}`. The signature protocol is unchanged (v1); there is no second,
shared bearer token.

A device reaches them only as an **active printer** whose enabled printer binding names an active
machine whose type has an **enabled `printer_agent` integration** in the same makerspace. Staff
manage those per-type bindings (`MANAGE_DEVICES` plus a machine scope covering the type):

- `GET|POST /api/v1/admin/makerspace/{makerspace_id}/machine-types/{type_id}/integrations` —
  `{"kind":"printer_agent","enabled":false,"config_schema_version":1}`; created **disabled** by
  default; `printer_agent` binds only the built-in 3D printer type (`400 integration_kind_unsupported`);
  a second binding of the same kind is `409 integration_exists`.
- `GET|PATCH|DELETE /api/v1/admin/machine-type-integrations/{id}` — only `enabled` and
  `config_schema_version` change. Bind, change and removal are audited
  (`devices.integration_bound|updated|unbound`).
- `GET /api/v1/admin/makerspace/{makerspace_id}/machine-types/{type_id}/integration-status` —
  read-only: each printer with an ENABLED binding on a machine of the type, its last-seen time and latest
  snapshot.

### Status snapshot on the heartbeat

`POST /api/v1/device/heartbeat` may carry a body (an empty body behaves exactly as before):

```json
{"status_snapshot": {"schema_version": 1, "observed_at": 1760000000, "state": "printing",
  "progress_percent": 42, "layer_current": 10, "layer_total": 200,
  "temperatures": {"nozzle": 215.4, "bed": 60, "chamber": null},
  "spools": [{"slot": 0, "material": "PLA", "colour": "Black", "remaining_percent": 80}],
  "clear_token": "bed-ok-1"}}
```

`state` is one of `idle`, `preparing`, `printing`, `paused`, `finished`, `failed`, `error`. Numbers
must be finite; out-of-range values are **clamped** (progress and spool remaining 0–100, layers
0–100000, nozzle −40–400 °C, bed −40–200 °C, chamber −40–120 °C). At most 16 spools, one per slot
(0–63); `material` ≤ 24 and `colour` ≤ 16 characters; `clear_token` 1–64 of `A-Z a-z 0-9 - _`.
Unknown fields, wrong kinds and sizes answer 400. The response adds `status_snapshot`:
`stored`, `stale` (not newer than the stored `observed_at`, so a retry is harmless), `throttled`
(within 5 seconds of the last stored one) or `not_integrated` (nothing stored). An `observed_at` more
than 5 minutes ahead is refused. One snapshot row is kept per device, overwritten in place; it is
advisory and never changes `Machine.status`, a request, consumption or money.

### Queue pull

`GET /api/v1/device/integrations/queue` (signed; sign the exact target and an empty body) returns
the machine and type it is bound to and up to 50 jobs: requests **accepted** for that machine type
(or that machine's legacy bucket) and the request **in progress** on that machine, oldest accepted
first. Each job carries `service_request_id`, `status`, `on_this_machine`, `estimated_minutes`,
`planned_grams`, `accepted_at`, `started_at` and the device's live `printer_job_id`, never a
requester, a title, a file or a storage location.

### Job reports

`POST /api/v1/device/integrations/jobs/{service_request_id}/report`:

- `{"event":"started","external_job_id":"agent-run-1"}` attaches the device to a request **staff
  already started** on its bound machine (starting chooses the material pool, a staff decision;
  otherwise `409 job_not_started`) and creates the acknowledged printer job. Repeating it is a no-op;
  another run on that request is `409 job_conflict`.
- `{"event":"completed"|"failed", "external_job_id", "operation_id", "actual_minutes",
  "consumptions", ...}` is the terminal report above (same fields, `event` in place of `outcome`;
  report the start first, else `409 job_not_reported_started`). A **failure is always held** for
  staff review (`needs_review`) whatever the binding's auto-apply policy; a completion follows
  `auto_apply_terminal`. Repeating the same operation is a no-op; changing it is 409. Staff apply a
  held report with `POST /api/v1/admin/printer-jobs/{id}/apply`; the effect runs through the
  machine-service workflow and its cost seam. Every report is audited
  (`machine_service.agent_report_applied|refused`).
