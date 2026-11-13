# Amazon Web Services

Read [hosting contracts](cloud-overview.md), [environment/setup](cloud-environment.md) and
[recovery](cloud-recovery.md) first. This recipe has not been deployed to a real AWS account for this
release; it is a documented mapping of the generic contract onto AWS services, validated statically
against the 0.12.0 environment surface. Verify prices, quotas and region availability in your account.

Run the setup wizard with provider **`docker`** (the rendered role/environment files are container
generic) and take the values it prints into the AWS services below.

| Need | AWS service | Notes |
| --- | --- | --- |
| Container image | Public image `ghcr.io/spaceworks-labs/spaceworks-backend@sha256:...`, or mirror it into ECR | App Runner and Fargate both pull ECR directly; use ECR pull-through cache for GHCR |
| PostgreSQL 16 | Amazon RDS for PostgreSQL 16 (or Aurora PostgreSQL 16) | Direct or session connections only. Never RDS Proxy in transaction-pooling mode. Enable `pgcrypto` and `pg_trgm` |
| Object storage | Amazon S3, two buckets | Full-parity store: presigned POST and PUT, versioning, Object Lock, list versions |
| Email | Amazon SES through django-anymail | `EMAIL_PROVIDER=ses`, region and credentials in the provider JSON file |
| Redis (optional) | ElastiCache for Redis/Valkey | Only for the Redis profile (worker and one beat). Brokerless needs none |
| Scheduler | EventBridge Scheduler or an ECS scheduled task | Only for the brokerless profile; see below |

## Choose a compute shape

| | App Runner (simplest) | ECS on Fargate (full) |
| --- | --- | --- |
| Roles you can run | `web` only: App Runner has no worker or scheduler service | `web`, `live`, `worker`, `beat` or `scheduler`, and a one-off `release` task |
| Profile | The [free profile](cloud-free.md): one web service and an external tick | Full Redis or full brokerless |
| Background work | Bounded work per tick; reminders can be late; no scheduled database dump | Native worker and scheduler |
| Use it for | A pilot or a very small space | Production |

Recommendation: App Runner for a pilot, ECS Fargate for production.

### 1. Network and database

1. Create a VPC with two private subnets for the database and tasks, and a public path (ALB for ECS,
   the managed endpoint for App Runner).
2. Create an RDS PostgreSQL 16 instance in the private subnets. Keep two logins: a finite maintenance
   (owner) login used only by the release task, and a narrow runtime login for the services
   (`DATABASE_URL`). Set `MANAGED_POSTGRES=True` only when the platform will not give you a superuser
   (Aurora, RDS) and `DATABASE_CONNECTION_MODE=direct`.
3. Store both URLs in Secrets Manager. The release task gets `DATABASE_MAINTENANCE_URL`; services never do.

### 2. Storage (full parity)

S3 supports everything the application can use, so describe it that way in the storage capabilities file:

- two buckets in one region: **private** (evidence, documents, backups) and **public image** (public-final
  images only), different names, both with Block Public Access on the private one;
- versioning enabled on the private bucket; Object Lock (compliance or governance mode) when you want
  tamper-evident retention, which must be chosen at bucket creation;
- a CORS rule on the private bucket allowing `PUT` and `POST` from your website origin (presigned uploads
  go straight from the browser), `ExposeHeaders: ETag`;
- an IAM user or role limited to those two buckets. On ECS or App Runner prefer the task/instance role;
  leave `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` empty and the SDK credential chain is used.

Environment: `AWS_STORAGE_BUCKET_NAME`, `PUBLIC_IMAGE_BUCKET`, `AWS_S3_REGION_NAME=<region>`,
`AWS_S3_ENDPOINT_URL=https://s3.<region>.amazonaws.com`, `AWS_S3_PUBLIC_ENDPOINT_URL` (the same value;
it is what the browser is given), `PUBLIC_IMAGE_BASE_URL` (the public bucket's HTTPS origin, ideally
CloudFront), `STORAGE_PRESIGN_METHOD=post` (S3 can enforce the size range at upload time) and
`STORAGE_CAPABILITIES_FILE` pointing at a Secrets Manager file or mounted secret.

### 3. Email (SES)

Verify the sending domain in SES and request production access. Set `EMAIL_PROVIDER=ses`,
`DEFAULT_FROM_EMAIL` to a verified sender and put the provider settings in the JSON file named by
`EMAIL_PROVIDER_CONFIG_FILE` (see the [environment page](cloud-environment.md)). Confirm a real message
reaches an inbox before accepting the deployment.

### 4a. App Runner (simple, free profile)

Create one service from the image with start command `--role backend python -m scripts.run_cloud_role web`,
port `8000`, health check path `/api/v1/health/readiness/`, an instance role for S3, a VPC connector for RDS
and the free-profile environment from `deploy/cloud/free.env.example`
(`SPACEWORKS_DEPLOYMENT_MODE=managed`, `SPACEWORKS_DEPLOYMENT_PROFILE=free`, `FREE_TICK_SECRET`, the free caps).
Run the **release** step first (step 6). Scheduled work comes from an EventBridge Scheduler schedule
(`rate(10 minutes)`) with an HTTPS API destination that `POST`s `{}` to
`https://<service>/api/v1/internal/free/tick` with the header `X-Cron-Secret: <FREE_TICK_SECRET>`; read
[the free guide](cloud-free.md) for the caps first.

### 4b. ECS Fargate (full)

One cluster, one task definition per role, all using the **same image digest**:

| Service | Command | Count | Credentials |
| --- | --- | --- | --- |
| web | `--role backend python -m scripts.run_cloud_role web` | 1+ behind an ALB (health `/api/v1/health/readiness/`) | runtime |
| live (optional, SSE) | `--role backend python -m scripts.run_cloud_role live` | 1, ALB rule `/api/v1/live/*`, idle timeout above 60 s | runtime |
| worker | `--role worker python -m scripts.run_cloud_role worker` | 1+ | runtime |
| beat (Redis profile) | `--role beat python -m scripts.run_cloud_role beat` | exactly 1 | runtime |
| release (one-off task) | `--role migrate python -m scripts.run_cloud_role release` | run to completion before traffic and on each upgrade | maintenance + runtime |

Redis profile: `CLOUD_TASK_PROFILE=redis`, `CLOUD_SCHEDULER=beat`, `CELERY_BROKER_URL` pointing at
ElastiCache (TLS `rediss://`). Brokerless profile: `CLOUD_TASK_PROFILE=brokerless`,
`CLOUD_SCHEDULER=loop` and a `scheduler` service (`--role cron python -m scripts.run_cloud_role scheduler`),
one task, interval 60 seconds or less.

### 5. Scheduled work (brokerless full, or the tick)

Every beat entry, including the 0.12 sweeps (guest passes and the post-event join follow-up ride the hourly
`run_membership_renewals_task`; loan pickup reminders ride `sweep_loan_pickups_task`), is in the scheduled-task
catalogue, so the `scheduler` role or the loop runs all of them. If you cannot keep a task running, use an ECS
**scheduled task** (EventBridge rule, rate 1 minute, `scheduler` role command with a short life) or EventBridge
Scheduler calling the free tick endpoint when you chose the free profile. Do not run two schedulers. The free profile uses the tick instead, which runs the same catalogue within its caps.

### 6. Release, then verify

```text
aws ecs run-task --cluster spaceworks --task-definition spaceworks-release --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-a],securityGroups=[sg-db-client],assignPublicIp=DISABLED}"
```

Then check `/api/v1/health/readiness/`, sign in as the first superadmin, create a loan and a booking, and send
a test email. YAML or CloudFormation rendering alone is not acceptance.

## Full or API-only

- **Full**: also run the website image `ghcr.io/spaceworks-labs/spaceworks-frontend` as an ECS service (port 80)
  behind the same ALB (default rule to the website, `/api/*`, `/static/*`, `/embed/*`, `/share/*`,
  `/.well-known/*` to the web service), or host the static build on S3 + CloudFront.
- **API-only (no web container)**: run only `web`, `live`, `worker`, `beat`/`scheduler`. Host the website on a
  static host ([adapters](cloud-static.md)) or serve a native app only. Set `PUBLIC_APP_BASE_URL` to the domain
  that should open emailed links, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `PLATFORM_STAFF_ORIGINS` to
  the website origin, `AUTH_COOKIE_SECURE=True`, `AUTH_COOKIE_SAMESITE=None` when the origins differ, and
  keep the ALB rules for the API paths only. Deny `/api/v1/internal/*` and `/api/v1/metrics*` at the ALB.

## Infrastructure as code

Terraform or CloudFormation for this is too long to be useful as a snippet and differs per organisation, so the
console steps above are the supported path. Every value is an ordinary service setting.

Wallet passes: the `WALLET_*_FILE` environment files need a durable volume shared by web and worker, which this recipe does not have. Enter the Apple/Google credentials in the console (Settings, Wallet passes) instead; they are stored encrypted ([wallet passes](../wallet-passes.md)).
