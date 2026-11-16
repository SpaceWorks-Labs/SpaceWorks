---
title: Cloud and providers
group: Hosting
order: 50
summary: The cloud and VPS recipes in the repository - AWS, Azure, Hetzner and Coolify, Render and more - plus the free profile and API-only setups.
---

# Cloud and providers

The simplest production setup is the [one-line installer](quick-install.md) on a VPS. This page lists the
other recipes that exist in the repository, what they need from you and what to keep in mind.

**Honest status.** The cloud recipes are configuration that was checked statically: the Compose files, Helm
chart, blueprints and environment lists were validated against the settings the backend reads. None of them
has been deployed to a real provider account for this release. Provider prices, quotas and screens change;
verify them in your own account.

## What every recipe needs

- The backend image from the registry, pinned by tag or digest.
- **PostgreSQL 16 or 17**, with the `pgcrypto` and `pg_trgm` extensions, over a direct or session connection.
  A transaction pooler is not supported, because the application holds advisory locks.
- **Two S3-compatible buckets**: a private one for evidence and documents and a public one for catalogue
  images.
- **A mail provider**: an HTTP API provider or SMTP.
- **Redis** for the Redis layout, or the brokerless layout (web, worker and a scheduler that runs at least
  every 60 seconds) with no Redis.

Run the setup wizard `scripts/init-cloud-environment.py` (provider `docker` is the generic choice) to render
the role and environment files, then run the finite release job to completion before starting traffic. See
[environment and setup](../deploy/cloud-environment.md), [hosting contracts](../deploy/cloud-overview.md) and
[recovery](../deploy/cloud-recovery.md).

## Recipes

| Recipe | Page | Notes |
| --- | --- | --- |
| VPS with the installer (Ubuntu, Debian) | [Hetzner and Coolify](../deploy/cloud-hetzner-coolify.md) | Option A is the one-line installer on a Hetzner VPS (4 GB RAM is comfortable). Option B uses Coolify. Both keep the full-server backup and rollback contract. |
| Oracle Always Free VM | [Oracle VM](../deploy/cloud-oracle-free.md) | The same installer as a paid VPS. Capacity and reclaim risks remain; check your own tenancy. |
| Amazon Web Services | [AWS](../deploy/cloud-aws.md) | App Runner or ECS Fargate, with RDS PostgreSQL 16, S3 and SES. |
| Microsoft Azure | [Azure](../deploy/cloud-azure.md) | Container Apps with PostgreSQL Flexible Server. Azure Blob is not S3-compatible, so use R2, B2 or S3 for files. |
| Render | [Render](../deploy/cloud-render.md) | Blueprints in `render.yaml` and `deploy/render*.yaml`. |
| Railway, Fly, Koyeb, DigitalOcean, Cloud Run | [Railway](../deploy/cloud-railway.md), [Fly](../deploy/cloud-fly.md), [Koyeb](../deploy/cloud-koyeb.md), [DigitalOcean](../deploy/cloud-digitalocean.md), [Cloud Run](../deploy/cloud-cloud-run.md) | Backend-role manifests under `deploy/`. |
| Kubernetes | [Kubernetes](../deploy/cloud-kubernetes.md), [Helm](../helm.md) | The chart in `charts/spaceworks`. PostgreSQL, Redis and S3 are external. |
| Plain Docker on any host | [Docker](../deploy/cloud-docker.md) | The `docker-compose.managed*.yml` files. |
| Static website | [Static frontend](../deploy/cloud-static.md) | Netlify, Cloudflare Pages or Workers, and Vercel adapters, keeping everything on one origin. |

### Services you can combine

| Service | Where it is documented |
| --- | --- |
| Supabase PostgreSQL (session pooler or direct) | [Supabase deployment](../supabase-deployment.md), [Hybrid setups](hybrid.md) |
| Cloudflare R2 (a limited store: presigned PUT, no versioning) | [Mix and match](../deploy/mix-and-match.md) |
| Resend, Postmark, Brevo, SES, Mailgun, SendGrid or SMTP | [Mix and match](../deploy/mix-and-match.md) |

Never grant a Supabase `anon`, `authenticated` or `service_role` role access to the application tables:
Django owns authorization.

## API-only setups

Every recipe runs in one of two forms. **Full** adds the website image to the backend roles. **API-only** has
no website container: the website lives on a static host, or only a mobile app and integrations use the API.

For a website on another origin, set the following on the backend:

- `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `PLATFORM_STAFF_ORIGINS` to the website origin exactly;
- `AUTH_COOKIE_SECURE=True` and `AUTH_COOKIE_SAMESITE=None`;
- `PUBLIC_APP_BASE_URL` to the domain emailed links should open;
- each space's `frontend_domain` to the website's domain.

Set `VITE_API_URL` on the static host to your API (for example `https://api.example.org/api`). Both sides must
be HTTPS. Because some browsers block third-party cookies across unrelated domains, put the website and API
under one parent domain (`app.example.org` and `api.example.org`). Keep `/api/v1/internal/*` and
`/api/v1/metrics*` unreachable from the internet.

For the installer, use `--frontend api-only`. For the other recipes, see the matrix under
[website: full or API-only](../deploy/cloud-overview.md#website-full-or-api-only).

## Free profile

The free profile is one small web container on a free tier, with an external database, storage and mail, and
a scheduled tick from a Cloudflare Worker or another trigger. The primary proposed stack is a free Render web
service, Supabase session PostgreSQL, Cloudflare R2, Resend or Brevo, and a Cloudflare cron trigger.

Understand what you give up: hard caps on rows, files and mail per tick, reminders that can be late, cold
starts, and no scheduled database dump. Live-account acceptance has not been recorded, so do not call it
certified free hosting. To prepare it on your own server, run `install.sh --profile free`; it writes a
private environment file with generated secrets and starts nothing. Read the [free guide](../deploy/cloud-free.md)
before relying on it.
