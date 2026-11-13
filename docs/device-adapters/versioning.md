---
title: Adapter API versioning
group: Reference
order: 64
summary: How the Device Adapter API changes without breaking adapters in other repositories.
---

# Versioning policy

- The URL carries the major version: `/api/v1/device/adapter/v1/`. A breaking change ships as `v2` beside `v1`;
  `v1` keeps working for at least one full release after `v2` is announced.
- `hello.protocol_version` is the integer the adapter speaks. The server answers with the version it speaks;
  v1 only accepts `1`.
- Each capability has its own `version` (declared in `hello`). New optional fields are added without a bump;
  a changed meaning or a removed field bumps the capability version and the old shape is served until the next
  major.
- Additive changes that never break an adapter: new capabilities, new optional request fields, new response
  fields, new reason or error codes, new event types. **Adapters must ignore response fields they do not know.**
  Request bodies are strict: unknown fields are `invalid_payload`, so an adapter cannot believe it set something it
  did not.
- The JSON Schemas under [`schemas/`](schemas/) are the contract. They are generated from the same dicts the server
  validates with (`scripts/export_adapter_schemas.py`), and a test fails if they drift.
- The signing scheme is the device protocol v1 and changes only with it ([device-protocol](../device-protocol.md)).
