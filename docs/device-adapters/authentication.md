---
title: Adapter authentication
group: Reference
order: 61
summary: How a device adapter enrolls, signs every request, and is revoked. It reuses the signed device protocol.
---

# Adapter authentication

An adapter is a `Device` of kind `adapter`. It authenticates exactly like every other device: an Ed25519
key pair it generates, a one-time enrollment token a staff member hands it, and a signature over every
request. The full byte-level specification and test vectors are in [Device protocol v1](../device-protocol.md);
this page is the adapter-author summary.

## Enroll (once)

1. Staff (`MANAGE_DEVICES`, switch `machines.integrations` on) call
   `POST /api/v1/admin/makerspace/{id}/devices` with `{"kind": "adapter", "name": "Workshop bridge"}`. The
   response carries `enrollment.token` **once**; it is never stored or shown again.
2. The adapter generates its key pair and calls `POST /api/v1/device/enrollments/{enrollment_id}/challenge` with
   the token and its public key, signs the returned challenge and calls `.../complete`. The device is now
   `active` with `key_version` 1.
3. The adapter calls `hello` (below) on every start.

## Sign every request

Headers on every call under `/api/v1/device/adapter/v1/`:

| Header | Value |
|---|---|
| `X-Device-Id` | the device UUID |
| `X-Device-Key-Version` | the current key version |
| `X-Device-Signature-Version` | `v1` |
| `X-Device-Timestamp` | Unix seconds; at most 300 s from the server clock (setting `DEVICE_SIGNATURE_MAX_SKEW_SECONDS`) |
| `X-Device-Nonce` | a fresh base64url nonce (16 to 64 bytes) per request |
| `X-Device-Signature` | base64 Ed25519 signature of the framed message |

The signed message frames: domain, version, method, the **raw request target** (path and query exactly as
sent), timestamp, nonce and the SHA-256 of the body. A nonce can be used once: the server remembers it for 24 hours
(`DEVICE_NONCE_TTL_SECONDS`, far longer than the skew window) and a replay is `401`. A timestamp outside the skew
window is `401`. A refusal by the tenant gate (`423`) consumes no nonce. There is no per-device rate limit on these
routes; `status` keeps one report per binding per five seconds (`throttled`) and detections are capped (`429`).

## Revocation and rotation

- Staff revoke a device with `POST /api/v1/admin/devices/{id}/revoke`; from that instant every call is `401` or
  `403` and queued commands are not delivered.
- Rotating the key (`POST /api/v1/admin/devices/{id}/enrollments`) bumps `key_version`; the old key's
  signatures die at once.
- A tenant frozen for migration answers `423`.

## What an adapter can and cannot do

- It can call only the routes in [api.md](api.md), only for **its own bindings**. A binding id that belongs to
  another adapter, or another makerspace, is `404`.
- It is never an audit actor (audit rows from adapter calls have no actor and carry the device id as metadata),
  never a user, holds no role and cannot call any `/api/v1/admin/` route.
- Every route is `404` while the space has `machines.integrations` off; a capability's child switch (`.access`,
  `.usage_billing`, `.video`, `.kiosk`, `.recording`, `.audio`, `.talk`, `.audio_recording`, `.artifacts`,
  `.detections`, `.telemetry_history`, `.diagnostics`, `.offline_cache`) hides only that capability's routes, and a
  command queued for a capability whose switch has since gone off is never delivered.
- Credentials it handles (card QR, NFC tag id, PIN) are used for one decision and never stored or logged by the
  server in the clear: NFC and PIN are kept as HMAC digests keyed by the deployment secret.
