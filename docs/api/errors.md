---
title: Errors
group: API
order: 40
summary: The error body shapes, status codes and the typed codes clients should handle.
---

# Errors

Errors come back with an HTTP status and a JSON body.

## Shapes

**Typed error.** Most refusals carry a human sentence and a stable machine code:

```json
{ "detail": "Confirm your identity to continue. Verification lasts ten minutes.", "code": "recent_reauth_required" }
```

Branch on `code`, never on `detail`: the sentence is translated, the code is not.

**Validation error.** A `400` maps each field to its messages:

```json
{ "email": ["Enter a valid email address."], "ordering": ["Unsupported sort field."] }
```

Some routes wrap this as `{"code": "invalid_input", "detail": "...", "fields": {...}}`.

**Module-off error.** A switched-off area or capability answers as if the route did not exist, but typed:

```json
{ "detail": "bookings is turned off for this makerspace.", "code": "module_disabled", "module": "bookings" }
```

For a capability the code is `feature_disabled` and the key is `feature`.

## Status codes

| Status | Meaning |
| --- | --- |
| 400 | Validation failed |
| 401 | Not signed in, or an API-client credential failed (a uniform `{"detail": "Invalid client signature."}`) |
| 403 | Signed in but not permitted, or a step-up is needed |
| 404 | Not found, not visible to you, or the module or capability is off |
| 409 | Conflicts with the current state (for example a stale or already-decided request) |
| 410 | Gone: retired or migrated and no longer served here |
| 415 | Unsupported media type |
| 423 | The space is frozen for tenant migration; the body has `detail` and `code` |
| 429 | Rate limit exceeded; see `Retry-After` |
| 500 | An internal or persistence failure |
| 503 | A required dependency is unavailable |

## Codes worth handling

| Code | Status | What to do |
| --- | --- | --- |
| `recent_reauth_required` | 403 | Ask the person to confirm their identity again (valid for ten minutes), then retry |
| `mfa_required` | 401 | Sign in again and complete two-step verification |
| `full_session_required` | 403 | The route is payout or reimbursement money and needs an interactive session, not a token or client |
| `module_disabled`, `feature_disabled` | 404 | The area is off for this space; hide the feature |
| `idempotency_key_reused` | 409 | The shop `Idempotency-Key` belongs to a different order; use a new key |
| `idempotency_key_required`, `invalid_idempotency_key`, `invalid_operation_id` | 400 | Send a UUID `Idempotency-Key` equal to the body's `operation_id` |
| `price_changed` | 4xx | A staff booking price confirmation is stale; preview again |
| `guardian_consent_required` | 4xx | A minor needs a signed guardian consent before this action |

Workflow refusals (for example issuing without a box scan or a return without a photo) also carry typed codes defined next to each route in its OpenAPI entry.

## Retrying

- `429` and `503`: retry with backoff, honouring `Retry-After` when present.
- `423`: wait; the space is mid-migration.
- `401` with `Invalid client signature.`: check the clock, nonce uniqueness and the exact signed path and body; the response never says which check failed.
- Other 4xx: do not retry unchanged.

## See also

- [Rate limits](rate-limits.md)
- [Idempotency](idempotency.md)
