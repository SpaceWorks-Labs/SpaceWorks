# Hosting Space Works

Start with [choose your hosting](../choose-your-hosting.md), which compares these with the self-hosted shapes.
Choose the operational contract before the provider. These recipes remain under integration;
source checks do not certify a deployment. Review the release acceptance report before enabling traffic.

| Setup | Selection | Processes | Recovery contract |
| --- | --- | --- | --- |
| Existing VPS / Compose | host + full (defaults) | Existing supervised stack | Existing H1 coordinated recovery |
| Paid managed Redis | managed + full | Web, worker, one elected beat; optional separate live | Provider recovery and independently qualified portable dumps |
| Paid managed brokerless | managed + full | Web, durable-work worker and scheduler <=60 seconds | Same managed limits |
| Additional free stack | managed + free | One web container and authenticated external tick | Best effort, caps/cold starts and independent recovery points |
| Free on your own server | managed + free, prepared by `install.sh --profile free` (opt-in) | Same single web container; the installer writes the private env and starts nothing | Same as the free stack |
| Oracle Always Free VM | host + full | Same supervised installer as a paid VPS | Full host contract; capacity/reclaim risks remain |

Read [environment/setup](cloud-environment.md) and [recovery](cloud-recovery.md).
Recipes: [Railway](cloud-railway.md), [Render](cloud-render.md), [Fly](cloud-fly.md),
[Koyeb](cloud-koyeb.md), [DigitalOcean](cloud-digitalocean.md), [Cloud Run](cloud-cloud-run.md),
[AWS](cloud-aws.md), [Azure](cloud-azure.md), [Hetzner and Coolify](cloud-hetzner-coolify.md),
[Docker](cloud-docker.md), [Kubernetes](cloud-kubernetes.md), [static frontend](cloud-static.md),
[free stack](cloud-free.md), [Oracle VM](cloud-oracle-free.md). Any compute, database, storage and email provider
combine: see [mix and match](mix-and-match.md).

Use PostgreSQL 16/17 with pgcrypto/pg_trgm and direct or session transport. Transaction pooling
cannot retain application advisory locks. Supabase session and Neon direct endpoints are substitutions,
not product classification: never invent PLATFORM_DOMAIN_SUFFIX to select managed mode. RDS,
DigitalOcean, Aiven, Railway and Render databases need the same transport, extension and privilege probes.
Use a non-owner runtime login, separate finite maintenance credentials and app-only grants. Supabase
anon/authenticated/service_role must have no access to Django tables, sequences or application functions.

Storage capabilities are independent: PUT/POST, conditional create, copy, multipart, history and Object Lock.
PUT validates byte length at finalization; POST can enforce its upload-time range. Private staging precedes
immutable final promotion. B2 history/lock support must be measured; lacking POST does not mean unversioned.
Bucket replacement needs verified migration plus retained old-locator cleanup. Choose nearby compatible
regions and record cross-provider egress; this does not promise residency.

Managed scanning defaults to none with a visible notice. Optional external ClamAV fails closed when selected.
Host upgrades retain explicit operator policy. Verify actual HTTP/SMTP mail receipt; console output is not
readiness. Finance encryption remains mandatory independently of optional PII. Full retains its existing
topology/binaries/quotas. Managed host controls refuse server-side: deploy through your cloud provider.
Image rollback does not reverse forward migrations. Preserve independently escrowed continuity keys.

## Website: full or API-only

Every recipe runs in one of two forms. **Full** adds the website image (`spaceworks-frontend`, or a static build)
to the backend roles. **API-only** has no web container: the website is hosted on a static host
([adapters](cloud-static.md)) or only a native app uses the API. Nothing else in the recipe changes; set
`PUBLIC_APP_BASE_URL` to the domain emailed links should open, and, when the website is on another origin,
`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `PLATFORM_STAFF_ORIGINS`, `AUTH_COOKIE_SECURE=True` and
`AUTH_COOKIE_SAMESITE=None`. Keep `/api/v1/internal/*` and `/api/v1/metrics*` unreachable from the internet.

| Recipe | Website service to add for Full | API-only means |
| --- | --- | --- |
| Render (`render.yaml`, `deploy/render*.yaml`) | Add a web service from the frontend image or a Render static site | The blueprints already contain only the backend roles: deploy them as they are |
| Railway, Fly, Koyeb, DigitalOcean, Cloud Run (`deploy/<provider>/`) | A second service from the frontend image, or a static host | The shipped manifests are backend-only: deploy them as they are |
| Docker (`docker-compose.managed*.yml`) | Add a `frontend` service from the image (see `docker-compose.cloud.yml`) | These files have no website service already |
| `docker-compose.cloud.yml` | Included (`frontend`) | Add `-f docker/compose.api-only.yml`: the website moves behind an inactive profile and an `api-edge` nginx exposes the API |
| Kubernetes (`charts/spaceworks`) | `frontend.enabled=true` (default) | `--set frontend.enabled=false`; the ingress then routes `ingress.apiOnlyPaths` to the backend and `/api/v1/live` to `live` |
| Installer / VPS (`docker-compose.prod.yml`) | Default | `install.sh --frontend api-only` (`docker/compose.api-only.yml`, `SPACEWORKS_RUN_FRONTEND=no`) |
| [AWS](cloud-aws.md), [Azure](cloud-azure.md), [Hetzner and Coolify](cloud-hetzner-coolify.md) | Add the frontend image as one more service | Omit it; each page has a Full or API-only section |
| [Free stack](cloud-free.md) | Static host through the Cloudflare/Vercel/Netlify adapter | The web container serves only the API; the website is always separate |
