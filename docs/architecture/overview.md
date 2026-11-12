---
title: Architecture overview
group: Architecture
order: 10
summary: The parts of a Space Works deployment and how they talk to each other.
---
# Architecture overview

Space Works is a set of thin clients over one API server. The API is built from deep modules (see [modules](modules.md)). Notifications flow **outward** to chat, email and messaging channels; nothing in chat can change the state of a request.

Three views, from the inside out. First, what runs in your deployment:

```mermaid
flowchart LR
  subgraph Clients
    SPA["React web app"]
    Mobile["Mobile and kiosk clients"]
    Ext["External systems<br/>API clients, tokens, OAuth apps"]
  end
  subgraph Server["Your deployment"]
    API["Django REST API"]
    Worker["Celery workers"]
    Beat["Celery beat"]
    DB[("PostgreSQL")]
    Redis[("Redis")]
    Store[("Object storage")]
  end
  SPA -->|"HTTPS JSON"| API
  Mobile --> API
  Ext -->|"signed or bearer requests"| API
  SPA -->|"direct upload, presigned URL"| Store
  API --> DB
  API --> Redis
  API -->|"presigned upload and read"| Store
  Beat --> Redis
  Redis --> Worker
  Worker --> DB
  Worker --> Store
```

Second, what leaves your deployment. Only the workers send messages; the API talks to payment rails and wallets directly:

```mermaid
flowchart LR
  Worker["Celery workers"] --> Chat["Telegram, Slack, Discord, Mattermost"]
  Worker --> Mail["Email provider"]
  Worker --> Msg["SMS and WhatsApp providers"]
  Worker --> Hooks["Signed webhooks"]
  API["Django REST API"] --> Pay["Payment rails<br/>Stripe, Razorpay"]
  Pay -->|"webhooks"| API
  API --> Wallet["Apple and Google Wallet"]
```

Third, the optional analytics tools, which read curated views and never write:

```mermaid
flowchart LR
  BI["Metabase or Grafana"] -->|"read-only login, curated views"| DB[("PostgreSQL")]
  BI -.->|"embedded dashboards"| SPA["React web app"]
```

## The parts

| Part | Role |
| --- | --- |
| **React web app** | The public inventory and event pages, the member area, and the staff console at `/admin`. It holds no business rules; the server decides. |
| **Django REST API** | Authentication, role checks, makerspace scoping, workflows and audit. Documented as OpenAPI at `/schema/`, with Swagger UI at `/docs/` and ReDoc at `/redoc/`. |
| **PostgreSQL** | The system of record. Database triggers back up the append-only rules for audit and evidence rows, and row-level security is a second tenant fence. |
| **Redis** | Cache and rate-limit state, and the broker for background jobs. |
| **Celery workers and beat** | Deliver notifications, expire evidence photo bytes, send reminders, run scheduled backups and other periodic work. |
| **Object storage** | A private S3-compatible bucket for evidence photos and other files. The standard install bundles Silo; you can use your own S3 or compatible service. Browsers upload with short-lived presigned URLs. |
| **Outbound channels** | Email, chat, SMS, WhatsApp and webhooks. See [integrations](integrations.md). |
| **Payment rails** | Optional online checkout. The ledger is core; the rail is removable. |
| **Metabase or Grafana** | Not bundled. Space Works gives each space a read-only database login over curated views. |

## What the standard Docker install runs

The Compose stack starts the database, Redis, object storage (plus a bucket setup job), a one-shot migration job and start-up safety check, the backend API, a live service for long-lived connections, Celery worker and beat, and the frontend. Other shapes (split website, cloud providers, a free profile) swap some of these for outside services. See [choose your hosting](../choose-your-hosting.md) and [mix and match](../deploy/mix-and-match.md).

## Request flow in one paragraph

A browser calls the API. Middleware identifies the caller (session, token, signed client or publishable key) and the makerspace. The view asks the Auth and RBAC module whether the actor may perform the action in that space. State changes go through the workflow module, quantity changes through the availability module, and the result is written to the audit log inside the same database transaction. After commit, notifications are queued for workers.

## Design rules that shape everything

- **Thin clients.** The web app, mobile apps and kiosks all use the same API.
- **One owner per rule.** State transitions live in one workflow module and quantity math in one availability module. See [modules](modules.md).
- **Tenant scoping on every query.** See [tenancy and roles](tenancy-and-roles.md).
- **Evidence and audit are append-only.** See [data and privacy](data-and-privacy.md).
- **Fail safe on outbound services.** A failed email, chat message or payment call must never crash a request.
