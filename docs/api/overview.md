---
title: API overview
group: API
order: 10
summary: The base URL, versioning, the interactive references and how to choose a credential.
---

# API overview

SpaceWorks exposes one REST API per deployment. The web console, the mobile apps and your own integrations all use it. This section holds the **guides**; a generated endpoint reference built from the OpenAPI schema lives separately in the app.

## Base URL and versioning

Everything is under `/api/v1/`, on the same host as your deployment (or the API host of a split install):

```text
https://spaces.example.org/api/v1/public/<makerspace-slug>/inventory/
```

- `/api/public/` is the frozen pre-v1 alias of the public catalogue.
- Additive changes (new fields, routes, scopes) land in v1. A breaking change gets a new prefix, and the old one is kept for at least one release.
- The schema always matches the running version.

## Interactive references

| Path | What it is |
| --- | --- |
| `/schema/` | The OpenAPI 3 document (`?format=json` for JSON) |
| `/docs/` | Swagger UI. Press **Authorize** and paste an access token under `jwtAuth` |
| `/redoc/` | ReDoc, the same reference grouped by area |

Swagger UI cannot compute request signatures, so use the snippets in [Authentication](authentication.md) for signed calls.

## What kinds of route exist

| Prefix | Who calls it |
| --- | --- |
| `/api/v1/public/` | Anyone, for a space's public catalogue, events, stats and so on; API clients may call the registered subset |
| `/api/v1/auth/` | Sign-in, refresh, logout, MFA and social sign-in |
| `/api/v1/member/` | A signed-in member, for their own data |
| `/api/v1/admin/` | Staff of a space (scoped to their roles), and platform superadmins |
| `/api/v1/events/` and `/api/v1/booking-integration/` | Signed integration reads by an API client |
| `/api/v1/oauth/` | The OAuth 2.0 provider for app connections |
| `/api/v1/webhooks/` | Inbound provider webhooks (payments), not for you to call |

> **Note** Routes under `/api/v1/admin/` are the staff console's own API. They are available to personal access tokens and app connections with a staff scope, and to nobody else outside a signed-in staff session.

## Choose a credential

| You are | Use | Acts as |
| --- | --- | --- |
| A backend of your own (ERP, script, sync job) | **API client** (signed server client) | The client, on public routes and signed integration reads |
| Another space's backend reading your public data | **API client**, type "Another space" | The client, read-only |
| A person automating their own work | **Personal access token** | That person, within the token's scopes |
| A third-party app that people sign in to | **App connection** (OAuth 2.0 with PKCE) | Each person who connects it |
| The SpaceWorks web app | Access token plus refresh cookie | The signed-in person |

No credential can do more than its owner may do at that moment.

## A first call

```bash
curl -s https://spaces.example.org/api/v1/public/lab/stats/
```

Public routes answer anonymously until the operator turns on `API_CLIENT_AUTH_REQUIRED`. See [Authentication](authentication.md) for what then applies.

## Conventions

- **Language.** Send `X-SpaceWorks-Locale: <code>` only for a deliberate choice; it outranks the account preference, the space default and `Accept-Language`. Codes, keys and enum values are never translated.
- **Pagination, errors and limits** follow one shape each: see [Pagination and filtering](pagination-and-filtering.md), [Errors](errors.md) and [Rate limits](rate-limits.md).
- **Module-off areas** answer as if the route did not exist (a typed 404).
- **Webhooks** go the other way: [Webhooks](webhooks.md).

## See also

- [API guide](../api-guide.md) (the long reference these pages summarise)
- [API client protocol](../api-client-protocol.md)
