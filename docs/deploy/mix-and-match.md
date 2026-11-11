# Mix and match: any compute, database, storage and email

Space Works does not care which company runs each part. It needs four things and one optional fifth:

1. **Compute**: somewhere to run the backend image (and optionally the website image).
2. **PostgreSQL 16 or 17**: any provider, direct or session connections.
3. **S3-compatible object storage**: two buckets, any provider.
4. **Email**: an HTTP API provider (through django-anymail) or SMTP.
5. **Redis** (optional): only for the Redis profile.

So "a VPS with Supabase, Cloudflare R2 and Resend" or "Render with Neon and Brevo" are ordinary choices. This page
gives the exact settings for each class, then three worked examples. Provider prices, free-tier limits and
region lists change; check them in your own account. None of these combinations has been run against a real
provider account for 0.12.0; the files and settings were checked statically.

```mermaid
flowchart LR
  compute["Compute<br/>VPS, Render, Fly, Cloud Run, Kubernetes"] --> db[("PostgreSQL 16 or 17<br/>bundled or any provider")]
  compute --> redis[("Redis, optional<br/>bundled, Upstash, or none")]
  compute --> store[("Two S3 buckets<br/>private and public images")]
  compute --> mail["Email<br/>API provider or SMTP"]
  local["Local default<br/>everything bundled on one server"] -.-> compute
```

## Pick the shape first

| You want | Use | Compute that fits |
| --- | --- | --- |
| Everything on one server, nothing external | The [installer](../install-and-update.md) | VPS (Hetzner, DigitalOcean, EC2, Oracle free) |
| The server plus any outside database, Redis, storage or email | The installer's **Outside services** step: [Hybrid setup](../install-and-update.md#hybrid-setup-outside-database-redis-storage-and-email) | VPS |
| Compute anywhere, database and storage as services | The cloud files (`docker-compose.managed.yml`, `docker-compose.managed-brokerless.yml`, `render.yaml`, `deploy/<provider>/`, `charts/spaceworks`) with `SPACEWORKS_DEPLOYMENT_MODE=managed` | VPS with Docker, Render, Railway, Fly, Koyeb, DigitalOcean App Platform, Cloud Run, [AWS](cloud-aws.md), [Azure](cloud-azure.md), [Coolify](cloud-hetzner-coolify.md), Kubernetes |
| The cheapest possible trial | The [free profile](cloud-free.md) | Render free web, Cloud Run, a free VPS |

The installer can now use an outside database and Redis as well as outside storage and email (see
[Hybrid setup](../install-and-update.md#hybrid-setup-outside-database-redis-storage-and-email)). The cloud files below are the
route when the backend itself runs on a platform (Render, Railway, Cloud Run, Kubernetes) rather than on a server you
install with `setup.sh`; they take any `DATABASE_URL` and run on a VPS too (Docker plus a reverse proxy such as Caddy for
HTTPS). The wizard `scripts/init-cloud-environment.py` generates every secret and key once; use provider `docker` for any
compute that is not named in its list.

## Database

| Setting | Value |
| --- | --- |
| `DATABASE_URL` | Narrow **runtime** login. `postgresql://runtime:...@host:5432/db?sslmode=require` (or `verify-full` with the provider CA) |
| `DATABASE_MAINTENANCE_URL` | Owner/maintenance login. Given only to the finite `release` job, never to resident services |
| `DATABASE_CONNECTION_MODE` | `direct`, or `session` for a session-mode pooler. **Never** transaction pooling: the application holds advisory locks |
| `MANAGED_POSTGRES` | `True` on any provider that does not give you a superuser (Supabase, Neon, RDS, Azure, Aiven, DigitalOcean) |
| Extensions | `pgcrypto`, `pg_trgm` |

| Provider | Which endpoint | Notes |
| --- | --- | --- |
| Supabase | Direct connection (5432), or the **session** pooler (5432 on the pooler host) | Not the transaction pooler (6543). Direct is IPv6-only on the free plan; use the session pooler from an IPv4-only host. `anon`, `authenticated` and `service_role` must have no access to the application's tables |
| Neon | The **direct** endpoint (host without `-pooler`) | Scale-to-zero adds a cold start; a slower tick cadence suits it |
| Amazon RDS / Aurora | Instance endpoint | Not RDS Proxy in transaction mode |
| Azure PostgreSQL Flexible | Server endpoint on 5432 | Allow-list the extensions in `azure.extensions` |
| Cloud SQL | Public IP with the Auth Proxy, or private IP | Direct connections |
| Self-run | Your own PostgreSQL 16 | Matching `pg_dump` major version for backups |

## Storage

Two buckets, always: **private** (evidence, documents, backups, never public) and **public image** (public-final
images only). Settings:

| Setting | Meaning |
| --- | --- |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | A key limited to those two buckets (empty on AWS when using a role) |
| `AWS_S3_ENDPOINT_URL` | The endpoint the **backend** uses |
| `AWS_S3_PUBLIC_ENDPOINT_URL` | The endpoint handed to **browsers** for presigned uploads and downloads. Must be a public HTTPS address |
| `AWS_S3_REGION_NAME` | The region (`auto` for R2) |
| `AWS_STORAGE_BUCKET_NAME`, `PUBLIC_IMAGE_BUCKET` | The private and the public bucket |
| `PUBLIC_IMAGE_BASE_URL` | The public HTTPS origin that serves the public bucket |
| `STORAGE_PRESIGN_METHOD` | `post` (size policy enforced at upload) or `put` |
| `STORAGE_CAPABILITIES_FILE` | Cloud files only: a strict version-1 JSON describing each bucket honestly |

The application detects and records what each store can do; it never pretends a weaker store is stronger (decision 37).

| Service | Presign | Versioning | Object Lock | Class |
| --- | --- | --- | --- | --- |
| Amazon S3 | `post` and `put` | yes | yes (set at bucket creation) | **Full parity** |
| Cloudflare R2 | `put` | no | no | Limited |
| Backblaze B2 (S3 API) | `put` | has file versions; measure before relying on them | has its own lock | Limited until measured |
| Supabase Storage (S3 API) | `put` | no | no | Limited |
| Hetzner Object Storage | `put` | provider dependent | provider dependent | Limited |
| GCS in S3-interop mode | `put` | by bucket setting, not through S3 calls | no | Limited |
| MinIO / Silo (self-run) | `post` and `put` | yes if enabled | yes if enabled | Full parity if you enable them |

In the capabilities file a limited store is `"presign_methods": ["put"]`, `"versioning": "never_versioned"` (or
`"unknown"`) and `"object_lock": false`. Limited means: the size of an upload is checked when it is finalised
rather than at upload time, there is no object history to recover an overwritten file from, and there is no
lock for tamper-evident retention. Evidence rows, scans and audit records live in the database either way.

**Browser-facing rules** (the most common cause of "uploads fail"):

- `AWS_S3_PUBLIC_ENDPOINT_URL` and `PUBLIC_IMAGE_BASE_URL` must be reachable by a visitor's browser and be HTTPS
  when the site is HTTPS. An internal address (`http://minio:9000`) only works on a single machine.
- Every private bucket needs a CORS rule allowing your website origin(s) with methods `PUT`, `POST`, `GET`,
  `HEAD`, any request headers and `ExposeHeaders: ETag`. For a platform with several space domains list each origin
  or use the provider's wildcard for your parent domain.
- The public bucket must be readable without signing (or served by a CDN) and must hold nothing private.

## Email

`DEFAULT_FROM_EMAIL` is a verified sender. Then either pick the provider in the settings console, or on cloud files
set `EMAIL_PROVIDER` and `EMAIL_PROVIDER_CONFIG_FILE` (a protected JSON file holding only these credential fields):

| `EMAIL_PROVIDER` | Fields |
| --- | --- |
| `resend` | `api_key` (optional `webhook_secret`) |
| `postmark` | `server_token` |
| `ses` | `region` and either `access_key_id` + `secret_access_key` (+ optional `session_token`) or `workload_identity: true` on AWS |
| `brevo` | `api_key` |
| `mailgun` | `api_key`, `domain`, `region` (`us` or `eu`) |
| `sendgrid` | `api_key` |
| `smtp` | The standard `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` settings |

Verify the domain (SPF and DKIM) with the provider and send a real message before accepting the deployment: console
output is not proof. Free email plans have daily caps; on the free profile set `FREE_EMAIL_DAILY_CAP`.

## Redis (optional)

Only the Redis profile needs it: `CLOUD_TASK_PROFILE=redis`, `CLOUD_SCHEDULER=beat`, `CELERY_BROKER_URL=rediss://...`
(Upstash, Redis Cloud, ElastiCache, Azure Cache, or your own). Without Redis choose `CLOUD_TASK_PROFILE=brokerless`
with `CLOUD_SCHEDULER=loop` (a scheduler process) or `external` (a cron calling the scheduler role), or the free
profile with its tick. The 0.12 periodic work (guest-pass expiry and notices, post-event join follow-ups, pickup
reminders) is part of the scheduled-task catalogue and runs in all of them.

## Origins and cookies

| Website and API are | Set |
| --- | --- |
| Same origin (a proxy routes `/api` to the backend) | `ALLOWED_HOSTS`, `PUBLIC_APP_BASE_URL`; cookies default correctly |
| Different origins | `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `PLATFORM_STAFF_ORIGINS` = the website origin; `AUTH_COOKIE_SECURE=True`, `AUTH_COOKIE_SAMESITE=None`; each space's `frontend_domain` is the website domain; prefer two hosts under one parent domain |
| Behind one proxy | `TRUSTED_PROXY_COUNT=1`, `TRUST_X_FORWARDED_PROTO=true` |

## Full or API-only

Every combination can run **Full** (the website image runs too) or **API-only** (no web container: the website is
hosted on a static host, or only a native app talks to the API). API-only drops the `spaceworks-frontend` service and
nothing else; the settings above do not change. Set `PUBLIC_APP_BASE_URL` to the domain that opens emailed links.
On the installer use `--frontend api-only`; on `docker-compose.cloud.yml` add `-f docker/compose.api-only.yml`; on
Helm set `frontend.enabled=false` (ingress then routes only the API paths, `ingress.apiOnlyPaths`).

## Worked example 1: VPS + Supabase + R2 + Resend

1. VPS with Docker and a reverse proxy (Caddy with automatic HTTPS in front of port 8000). DNS `A` record
   `api.example.org`.
2. Supabase project: take the **session pooler** URL for `DATABASE_URL` (runtime role you created) and the direct
   or session URL of the postgres owner for `DATABASE_MAINTENANCE_URL`. `MANAGED_POSTGRES=True`,
   `DATABASE_CONNECTION_MODE=session`.
3. R2: two buckets (`sw-private`, `sw-public`), an API token limited to them, the public bucket on a custom domain
   `img.example.org`. `AWS_S3_ENDPOINT_URL=AWS_S3_PUBLIC_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com`,
   `AWS_S3_REGION_NAME=auto`, `STORAGE_PRESIGN_METHOD=put`, `PUBLIC_IMAGE_BASE_URL=https://img.example.org`,
   capabilities file with `presign_methods:["put"]`, `versioning:"never_versioned"`. Add a CORS rule on `sw-private`.
4. Resend: verify the domain, `EMAIL_PROVIDER=resend`, config file `{"api_key": "re_..."}`.
5. Run the wizard (provider `docker`), copy `docker-compose.managed.yml` and the env files to the VPS, run the
   `release` service, then `docker compose -f docker-compose.managed.yml up -d backend worker beat`. Add Redis
   (the compose file expects a broker) or use `docker-compose.managed-brokerless.yml`.
6. Website: static host, or the frontend image behind the same Caddy.

## Worked example 2: Render + Neon + R2 + Brevo (free tier)

1. Neon: a project; the **direct** endpoint URL for `DATABASE_URL` and the same with the owner role for
   `DATABASE_MAINTENANCE_URL`; `DATABASE_CONNECTION_MODE=direct`, `MANAGED_POSTGRES=True`. Use a slower tick (see
   [the free guide](cloud-free.md)) so the database can pause.
2. R2 as above (free allowance).
3. Brevo: verify the sender, `EMAIL_PROVIDER=brevo`, config `{"api_key": "xkeysib-..."}`; set `FREE_EMAIL_DAILY_CAP`
   to the plan's daily limit and `FREE_EMAIL_ACCOUNT_KEY`.
4. Render: create the service from `deploy/render.free.yaml` (one web service on the free plan), fill the secrets,
   run the release step once.
5. Scheduler: a Cloudflare Worker cron (`deploy/static/cloudflare/free/`) or another trigger in
   `deploy/cloud/free-triggers/` calling the tick every 10 minutes (`X-Cron-Secret`). Reminders can be late; there is no
   scheduled database dump, so take an external backup.
6. Website on Cloudflare Pages (free) through the [static adapter](cloud-static.md).

## Worked example 3: Cloud Run + Cloud SQL + GCS (S3 interop) + SES

1. Cloud SQL for PostgreSQL 16 with a runtime and a maintenance user; connect through the Cloud SQL connector or
   private IP (direct). `MANAGED_POSTGRES=True`.
2. GCS with HMAC keys for a service account and the S3-interoperability endpoint `https://storage.googleapis.com`:
   `AWS_S3_ENDPOINT_URL=AWS_S3_PUBLIC_ENDPOINT_URL=https://storage.googleapis.com`, region `auto`,
   `STORAGE_PRESIGN_METHOD=put`. GCS interoperability does not provide presigned POST, S3 versioning calls or
   Object Lock: describe it as a **limited** store. Set a bucket CORS policy (`gsutil cors set`) for your website origin.
3. SES (in AWS) for mail: verify the domain, create a restricted IAM user, `EMAIL_PROVIDER=ses`, config
   `{"region": "eu-west-1", "access_key_id": "...", "secret_access_key": "..."}`.
4. Cloud Run: use `deploy/cloud-run/` (`web.yaml`, `worker.yaml`, `beat.yaml`, `release-job.yaml`). Run `release-job`
   first. For brokerless use `scheduler.yaml` or `scheduler-job.yaml` with Cloud Scheduler. Secrets come from
   Secret Manager mounted as files (`STORAGE_CAPABILITIES_FILE`, `EMAIL_PROVIDER_CONFIG_FILE`).
5. Website: Cloudflare Pages, Vercel or Netlify with [static adapters](cloud-static.md), or API-only for an app.

## Check before you rely on it

Health endpoint, first superadmin sign-in, create an item and a loan with a photo (upload goes to storage and
reads back), a booking, a test email, and a scheduled sweep running (the audit log or the problem reports show
progress). [Recovery](cloud-recovery.md) says what each combination can and cannot restore.
