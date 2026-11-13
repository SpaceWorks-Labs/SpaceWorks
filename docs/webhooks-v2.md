# Signed webhook v2

Choose payload format 2 on a signed-webhook destination. Existing destinations remain
on v1 until explicitly changed. Slack, Discord and Mattermost message formats are unchanged.

```json
{
  "version": 2,
  "id": "42",
  "event": "hardware_requests.accepted",
  "makerspace_id": 7,
  "occurred_at": "2026-10-11T00:00:00+00:00",
  "data": {"request_id": 123}
}
```

The complete [JSON Schema catalogue](webhooks-v2.schema.json) uses Draft 2020-12.
Its `$defs` contains one schema for every matrix event, `system.delivery_test`, and
`reports.scheduled_report`; the top-level `oneOf` selects the event. Envelope and data
objects reject extra fields. Data properties are optional positive integer IDs. Missing
IDs are omitted; Boolean, string and foreign-family IDs are refused. No chat text,
rendered template context, email/phone, provider handles, credentials, report download
URLs or free-form audit metadata travel in v2.

| Family | Allowed data properties |
| --- | --- |
| hardware_requests | request_id, payment_id |
| printing | machine_service_request_id, request_id, machine_id |
| events | event_id, series_id, registration_id |
| bookings | booking_id, space_id |
| maintenance | machine_id, schedule_id, maintenance_log_id |
| members | membership_request_id, membership_id |
| api_access | api_key_request_id |
| devices | none |
| presence | none |
| payments | payment_id, refund_id, request_id, booking_id, registration_id, membership_id |
| stock | to_buy_item_id, pool_id |
| certifications | certification_grant_id, certification_type_id, membership_id |
| reports | schedule_id |
| system.delivery_test | none |

`id` is the delivery log ID as a string, stable across retries of that log. Distinct
rooms receive distinct delivery IDs. `occurred_at` snapshots event time before
on-commit/queue delay; older logs fall back to creation time. `event` and
`X-SpaceWorks-Event` use the stable `family.event` key. Consumers deduplicate by
deployment and delivery ID. Delivery is at least once, not exactly once.

The signature contract is unchanged: `X-SpaceWorks-Signature` contains
`t=<unix_seconds>,v1=<hex HMAC-SHA256(secret, <t> + '.' + exact_body_bytes)>`.
Reject stale timestamps, compare signatures in constant time, and verify before
parsing JSON. Header signature version `v1` identifies the HMAC algorithm, independently
of payload format 2. `X-SpaceWorks-Delivery` carries the log ID; User-Agent is
`SpaceWorks-Webhook/2`. The timestamp/signature change on retry, while event data stays
stable. Existing SSRF validation, DNS pinning, redirect checks and encrypted per-room
secrets still apply.

Changing the schema requires updating the runtime catalogue and snapshot together.
Consumers should pin a schema version and deliberately opt in to future breaking formats.


## Damaged-return handoff and `issue_reported`

`issue_reported` is named per area family, not per source. A damaged-return handoff to repairs
raises the same event as a member's own report, and it fires the event of the
item's area, once, on first creation only (an idempotent replay never alerts twice):

| Item's area | Event |
|---|---|
| Inventory item | `hardware_requests.issue_reported` |
| Bookable room or space | `bookings.issue_reported` |
| Machine | `maintenance.issue_reported` (the machines area's webhook family is `maintenance`) |

The payload is the family's usual identifier set; consumers that handle all three families can
subscribe to each name separately.

## Signing secret: shown once, and rotation

For a signed-webhook destination the server makes the signing secret, not you. It looks like `whsec_...` and is returned **once**, in the response that creates the destination (or that rotates it). It is stored encrypted and no screen or API ever shows it again, so copy it into your receiver straight away. If you lose it, rotate.

Rotate from the destination in the space's notification settings, or with `POST /api/v1/admin/makerspace/{id}/notification-destinations/{destination_id}/rotate-secret`. It needs the manage-space permission and only applies to signed-webhook destinations. The optional body `grace_hours` is a whole number from 0 to 168, 24 by default.

During the grace window the old secret keeps working next to the new one. Each delivery's `X-SpaceWorks-Signature` then carries one `v1=` value per live secret, newest first:

```
t=1760000000,v1=<hmac with the new secret>,v1=<hmac with the old secret>
```

A receiver can therefore deploy the new secret first and accept a delivery when **any** `v1=` value matches. When the window ends the header goes back to a single value. A grace of `0` retires the old secret immediately, so deliveries sign with the new secret only. Every rotation is written to the audit log (`notification_destination.secret_rotated`) with the grace hours, never the secret.
