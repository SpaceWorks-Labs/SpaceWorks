---
title: Idempotency
group: API
order: 70
summary: How to retry safely, the Idempotency-Key header on shop orders and command routes, and payment checkout.
---

# Idempotency

A network call can fail after the server has already acted. Idempotency lets you retry without doing the thing twice.

## Shop orders: optional key

`POST /api/v1/public/m/<slug>/shop/orders/` (placing an order) accepts an optional `Idempotency-Key` header of up to 64 characters.

- A repeat with the **same key** in the same space returns the **first order** (and its charge) instead of placing a second.
- If the key belongs to a different order, the server refuses it with `409 idempotency_key_reused`.
- Generate one key per customer intent (for example a UUID created when the checkout form opens) and reuse it on every retry.

```bash
curl -X POST https://spaces.example.org/api/v1/public/m/lab/shop/orders/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 0b1c6a52-8f1e-4f55-9a63-2d0c2a7d4e11" \
  -H "Content-Type: application/json" -d @order.json
```

## Command routes: required key equal to `operation_id`

Several write routes (saved details, event staged forms, judging, hackathon and contribution commands, certificate seeds, payout exports) are **commands**. They need:

- an `operation_id` UUID in the body, and
- an `Idempotency-Key` header equal to that UUID.

A missing or mismatched header answers `400` with a code such as `idempotency_key_required`, `invalid_idempotency_key`, `invalid_operation_id` or `idempotency_key_mismatch`. A replay needs the **identical body and route**; the server then returns the original outcome rather than acting again. The OpenAPI entry marks the header as required wherever it is.

## Payments

Online checkout is protected on the server: each payment's checkout call to the provider carries a key derived from the payment itself, so a retried or concurrent checkout cannot create two charges for one payment. You do not send a header for this. Provider webhooks are likewise de-duplicated on the server.

## Webhooks you receive

Outbound webhooks are delivered **at least once**. De-duplicate on the deployment plus `X-SpaceWorks-Delivery`. See [Webhooks](webhooks.md).

## Good practice

1. Create the key **before** the first attempt and persist it with your pending action.
2. Reuse it unchanged on retries; never reuse it for a different action.
3. Treat the first response as final, even if you only receive it on a retry.

## See also

- [Errors](errors.md)
- [Rate limits](rate-limits.md)
