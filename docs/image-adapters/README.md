---
title: Image Adapter API v1
group: Reference
order: 61
summary: The contract any HTTPS service implements so SpaceWorks can remove the background from card photos. Build and run your own provider.
---

# Image Adapter API v1

SpaceWorks never bundles an image model and never sends a photo to a third-party cloud by default. Instead it
speaks one small, versioned contract. **SpaceWorks is the client; a provider is any HTTPS service that implements
the contract.** You build and run the provider (a few dozen lines in any language), then connect it in
**Platform settings › Background eraser** (for the whole server) or **Settings › Background eraser** (for one
space).

This is the same philosophy as the [Device Adapter API](../device-adapters/README.md): one uniform contract, adapters
live in their own repositories.

## Capabilities

A provider declares what it can do in its health answer. v1 has one capability; adding an image operation later is
one entry in `backend/apps/card_designs/image_adapter/contract.py` (`CAPABILITIES`) plus its schema here.

| Capability | Path | What it does |
|---|---|---|
| `image.remove_background` | `POST /v1/remove-background` | Returns the subject of a photo on a transparent background. |
| (health) | `GET /v1/health` | Signed liveness and capability check, used by **Test connection**. |

## Pages in this folder

- [Requests, responses and limits](api.md): what SpaceWorks sends, what you answer, size and type limits, a `curl` example.
- [Authentication](authentication.md): the HMAC-SHA256 signature, replay protection, and a verifier you can copy.
- [Errors](errors.md): the typed error codes and which are retried.
- [Build a provider](build-a-provider.md): a minimal pseudo-implementation and a conformance checklist.

## Versioning

The version is `1` and is sent in the `X-SW-Adapter-Version` header. A provider must answer `"contract": "1"` from
`/v1/health`. A breaking change becomes `/v2/...` with a new header value; v1 paths, headers and error codes never
change meaning. New optional fields may be added to v1 answers: ignore fields you do not know.

## Privacy

The photo is sent only when staff press **Remove background** on a card photo, when a member asks for it on their
own card (after agreeing), or when staff tick **Remove backgrounds after upload** in a bulk photo upload. Run your
provider where you are comfortable holding that photo; it should not store the image after answering. See
[Background eraser](../how-to/background-eraser.md) for the operator's view.
