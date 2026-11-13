---
title: Build an adapter in another repository
group: Reference
order: 65
summary: A step-by-step guide to writing a vendor adapter against the Device Adapter API and proving it with the conformance kit.
---

# Build an adapter in another repository

Vendor adapters (Bambu, Prusa, OctoPrint, Klipper, a laser or CNC controller, a shelf pointer, a door lock) never
live in this repository. They speak only the contract in this folder.

## Recommended layout

```
my-adapter/
  adapter/            # your code: one module per vendor protocol
  schemas/            # a copy of docs/device-adapters/schemas/*.json (validate before sending)
  config.example.toml # SpaceWorks URL, device id, key path, bindings (external_ref -> vendor id)
  tests/              # the conformance run below, in CI against a dev server
```

## The loop

1. **Enroll once** ([authentication](authentication.md)). Keep the private key on the bridge, readable by the
   adapter only.
2. **`hello`** on start with your `adapter_kind` and the capabilities you really implement. Read `bindings`.
3. Every `poll_seconds`: `POST status` for each binding (state, progress, error codes), `POST commands/lease` and
   execute what you get, then `POST commands/{id}/ack`. Send `events` as things happen, with a fresh
   `operation_id` per event (retry the same one until it answers).
4. Re-read `GET bindings` when the `config_version` in a response changes.
5. Never decide on your own. Access and session decisions come from SpaceWorks (`access/authorize`,
   `sessions/start`); a `denied` never alters a running session; if the server is unreachable, fail closed.
6. Keep vendor credentials (printer API keys, door codes) on the bridge. SpaceWorks never asks for them.

## Prove it: the conformance kit

`backend/tests/adapter_conformance/` contains a signed client, a mock adapter and the checks (hello, bindings, status
idempotency and validation, event idempotency, undeclared-capability refusal, replay and stale-timestamp refusal,
command lease and ack) plus the contract rails in `rails.py` (unsigned and tampered requests, strict bodies, ids
that are not yours, typed refusals across the job, kiosk, media, session, usage and config routes). Against a dev
server:

```
# in the SpaceWorks repo, from backend/
python -I -m tests.adapter_conformance.run --url https://dev.example \
  --device <device uuid> --key-version 1 --private-key <base64 raw key> --binding <binding uuid> --expect-command
```
Prepare the space: switch `machines.integrations` on, enroll an adapter (`kind: "adapter"`), bind a machine with
`events` and `control`, and (for `--expect-command`) queue one `control/pause` command from the console. Exit code 0
means every check passed. The kit imports only `apps.devices.protocol` and `apps.ed25519` (stdlib and
`cryptography`); re-implement those few lines in your language from the [protocol vectors](../device-protocol.md).

## Rules your adapter must keep

- Poses, locations and boxes are staff data; never show them to members.
- Never record or forward video unless a watch session is open; never persist frames.
- Treat `404` as "not available", `401` as "re-sign", `403` as "stop".
