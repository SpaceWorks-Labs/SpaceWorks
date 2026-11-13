---
title: Webhooks
group: API
order: 60
summary: Outbound signed webhooks, payload versions 1 and 2, verifying signatures and delivery behaviour.
---

# Webhooks

SpaceWorks can call **your** HTTPS endpoint when something happens (a request accepted, a booking confirmed, a payment settled). This is the reverse of the API: you receive, you verify, you reply 2xx.

## Create an endpoint

1. In **Settings > Communication > Notifications**, press **Add a room** and pick the **Signed webhook** channel.
2. Enter the room name, the HTTPS URL and a **Signing secret** (at least 16 characters).
3. Choose the **Payload format**: v1 legacy envelope or v2 structured domain IDs.
4. Choose events in the notification matrix. Test from the delivery screen.

The URL must be public HTTPS. Private and loopback addresses are refused when you save and again when sending, and redirects are checked.

## Request

`POST` with `Content-Type: application/json` and these headers:

| Header | Value |
| --- | --- |
| `X-SpaceWorks-Event` | Event key. v1: the bare key (`accepted`). v2: `family.event` (`hardware_requests.accepted`) |
| `X-SpaceWorks-Delivery` | The delivery log ID, stable across retries. Use it to de-duplicate |
| `X-SpaceWorks-Signature` | `t=<unix seconds>,v1=<hex HMAC-SHA256>` |
| `User-Agent` | `SpaceWorks-Webhook/1` or `SpaceWorks-Webhook/2` |

## Payload version 2

```json
{
  "version": 2,
  "id": "42",
  "event": "hardware_requests.accepted",
  "makerspace_id": 7,
  "occurred_at": "2026-10-11T00:00:00+00:00",
  "data": { "request_id": 123 }
}
```

- `data` holds only optional positive integer IDs for the event's family (for example `request_id`, `payment_id`, `booking_id`, `event_id`, `registration_id`, `machine_id`). Absent IDs are omitted.
- No chat text, contact details, provider handles, credentials or free-form audit data travel in v2.
- The JSON Schema (Draft 2020-12) is in [webhooks-v2.schema.json](../webhooks-v2.schema.json); envelope and data objects reject extra fields.
- `id` is the delivery log ID as a string. Distinct rooms get distinct IDs.

Payload v1 keeps the older envelope (`id`, `event`, `feature`, `makerspace_id`, `text`, `data`, `created_at` and a `structured` object). New integrations should choose v2. Details of both: [Signed webhook v2](../webhooks-v2.md) and [API client protocol](../api-client-protocol.md#outbound-webhooks).

## Verify the signature

Compute `HMAC-SHA256(secret, "<t>." + raw_body_bytes)`, compare with `v1` in constant time and reject stale timestamps (five minutes is reasonable). Verify **before** parsing JSON.

```python
import hashlib, hmac, time

def verify(headers, raw_body: bytes, secret: str, tolerance=300) -> bool:
    parts = dict(item.split("=", 1) for item in headers["X-SpaceWorks-Signature"].split(","))
    if abs(time.time() - int(parts["t"])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

## Delivery behaviour

- Reply with any `2xx`. Anything else, or a timeout (about five seconds), counts as a failure.
- Delivery is **at least once**. De-duplicate on the deployment plus `X-SpaceWorks-Delivery`.
- Failed deliveries are retried by the delivery worker. After the retries a space manager can retry from **Delivery logs**, or a superadmin from `/control/`.
- On a retry the timestamp and signature change; the event data stays the same.
- Secrets are stored encrypted per room.

## Events

The v2 catalogue covers hardware requests, printing, events, bookings, maintenance, members, API access, devices, presence, payments, stock, certifications and scheduled reports, plus `system.delivery_test`. An area's `issue_reported` event is named for the item's area: `hardware_requests.issue_reported`, `bookings.issue_reported` or `maintenance.issue_reported`.

## See also

- [Signed webhook v2](../webhooks-v2.md)
- [Idempotency](idempotency.md)
