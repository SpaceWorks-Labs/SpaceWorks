# Microsoft Azure

Read [hosting contracts](cloud-overview.md), [environment/setup](cloud-environment.md) and
[recovery](cloud-recovery.md) first. This recipe has not been deployed to a real Azure subscription for this
release; it maps the generic contract onto Azure services and was validated statically against the 0.12.0
environment surface. Verify prices, quotas and region availability in your subscription.

Run the setup wizard with provider **`docker`** and carry its values into the services below.

| Need | Azure service | Notes |
| --- | --- | --- |
| Compute | Azure Container Apps (one environment) | Apps for `web`, `live`, `worker`, `beat`; a Job for `release`; a scheduled Job for the brokerless scheduler |
| PostgreSQL 16 | Azure Database for PostgreSQL Flexible Server 16 | Direct connections (port 5432), not the built-in PgBouncer in transaction mode. Allow extensions `pgcrypto` and `pg_trgm` (server parameter `azure.extensions`) |
| Object storage | See "Storage" below: use Cloudflare R2, Backblaze B2 or Amazon S3 unless you run an S3 gateway | Azure Blob is **not** S3-compatible |
| Email | Any anymail provider: Resend, Postmark, Brevo, Mailgun, SES, SendGrid, or SMTP | Azure Communication Services Email has no anymail backend here; use its SMTP relay only if it fits your policy |
| Redis (optional) | Azure Cache for Redis, TLS port 6380 (`rediss://`) | Only for the Redis profile |

## Storage: the honest limits

SpaceWorks speaks the S3 API. Azure Blob Storage does not, so there are three choices:

1. **Recommended: an S3-compatible service outside Azure** (Cloudflare R2, Backblaze B2, Amazon S3). The
   application and database stay in Azure and only objects live elsewhere. Browsers upload to the storage
   service directly, so there is no extra hop on the app path.
2. **An S3 gateway in front of Blob** (for example MinIO gateway-style projects or a self-run S3 proxy). This
   is third-party software you must run and patch. A gateway generally gives presigned `PUT` but not presigned
   `POST` size policies, versioning, Object Lock or conditional create, so describe it as a **limited** store in
   the capabilities file (`presign_methods: ["put"]`, `versioning: "never_versioned"`, `object_lock: false`).
   Features that need those capabilities show a clear notice instead of working weakly (decision 37).
3. **Run MinIO/Silo yourself** on a VM with a managed disk: full control, but you own durability and backups.

Whatever you choose, keep two buckets (private and public image), add a CORS rule for your website origin
(`PUT`/`POST`, `ExposeHeaders ETag`), and set `AWS_S3_ENDPOINT_URL`, `AWS_S3_PUBLIC_ENDPOINT_URL`,
`AWS_S3_REGION_NAME` (`auto` for R2), `AWS_STORAGE_BUCKET_NAME`, `PUBLIC_IMAGE_BUCKET`, `PUBLIC_IMAGE_BASE_URL`,
`STORAGE_PRESIGN_METHOD` (`put` for R2/B2/gateways, `post` for S3) and `STORAGE_CAPABILITIES_FILE`.
See [mix and match](mix-and-match.md#storage) for the per-service capability values.

## Steps

1. Create a resource group, a Log Analytics workspace and a Container Apps environment in one region
   (use a VNet-integrated environment if you restrict the database to a private endpoint).
2. Create the Flexible Server (PostgreSQL 16). Create a maintenance (owner) login for the release Job only and a
   narrow runtime login for the apps. Put both URLs in Container Apps secrets or Key Vault references.
3. Create the storage (above) and the email provider; write the two secret JSON files
   (`STORAGE_CAPABILITIES_FILE`, `EMAIL_PROVIDER_CONFIG_FILE`) as Container Apps secret volumes.
4. Create the **release Job** (manual trigger, same image digest):
   `az containerapp job create ... --trigger-type Manual --command "--role migrate python -m scripts.run_cloud_role release"`
   with the maintenance secrets, and run it with `az containerapp job start`. Wait for success before any app starts.
5. Create the apps from the same image digest:

| App | Command | Ingress | Replicas |
| --- | --- | --- | --- |
| web | `--role backend python -m scripts.run_cloud_role web` | external, port 8000, health `/api/v1/health/readiness/` | 1+ |
| live (optional) | `--role backend python -m scripts.run_cloud_role live` | same hostname, path `/api/v1/live/`, or its own | 1 |
| worker | `--role worker python -m scripts.run_cloud_role worker` | none | 1+ |
| beat (Redis profile) | `--role beat python -m scripts.run_cloud_role beat` | none | exactly 1 (min = max = 1) |

   Redis profile: `CLOUD_TASK_PROFILE=redis`, `CLOUD_SCHEDULER=beat`, `CELERY_BROKER_URL=rediss://...`.
   Brokerless profile: `CLOUD_TASK_PROFILE=brokerless`, `CLOUD_SCHEDULER=loop` and a `scheduler` app
   (`--role cron python -m scripts.run_cloud_role scheduler`, one replica), or `CLOUD_SCHEDULER=external` with a
   scheduled Job (`--trigger-type Schedule --cron-expression "* * * * *"`) running the same scheduler role.
6. Set the exact origins (`ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`,
   `PLATFORM_STAFF_ORIGINS`, `PUBLIC_APP_BASE_URL`), `TRUSTED_PROXY_COUNT=1`, `TRUST_X_FORWARDED_PROTO=true`.
7. Verify health, first sign-in, a loan, a booking, an uploaded photo and a real email.

Every beat entry, including the 0.12 sweeps (guest passes and the post-event join follow-up ride the hourly
`run_membership_renewals_task`; pickup reminders ride `sweep_loan_pickups_task`), runs through the scheduler role,
the loop or the scheduled Job. The free profile (one web app plus an external tick) also fits Container Apps with
a scale-to-zero floor of 1; see [the free guide](cloud-free.md).

## Full or API-only

- **Full**: add one more app from `ghcr.io/spaceworks-labs/spaceworks-frontend` (port 80, env `TENANT_API_URL=/api`
  or your API origin) and route `/` to it, `/api`, `/static`, `/embed`, `/share`, `/.well-known` to `web`. Or use
  Azure Static Web Apps / Storage static website / any static host for the build.
- **API-only (no web container)**: deploy `web`, `live`, `worker` and `beat`/`scheduler` only. Host the website on a
  static host ([adapters](cloud-static.md)) or serve a native app only. Set `PUBLIC_APP_BASE_URL` to the domain that
  should open emailed links; set the CORS/CSRF/staff origins to the website origin, `AUTH_COOKIE_SECURE=True` and
  `AUTH_COOKIE_SAMESITE=None` when the origins differ. Block `/api/v1/internal/*` and `/api/v1/metrics*` at the edge.

Wallet passes: the `WALLET_*_FILE` environment files need a durable volume shared by web and worker, which this recipe does not have. Enter the Apple/Google credentials in the console (Settings, Wallet passes) instead; they are stored encrypted ([wallet passes](../wallet-passes.md)).
