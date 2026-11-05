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
[Docker](cloud-docker.md), [Kubernetes](cloud-kubernetes.md), [static frontend](cloud-static.md),
[free stack](cloud-free.md), [Oracle VM](cloud-oracle-free.md).

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
