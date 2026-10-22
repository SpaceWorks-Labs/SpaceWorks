# Supabase PostgreSQL substitution

Supabase supplies PostgreSQL; Django owns authorization. Never grant anon/authenticated/service_role access to
Django tables/functions/sequences or replace Django authentication with Supabase Auth/Data API. A fake platform
suffix is not managed admission. Read [setup](deploy/cloud-environment.md) and [hosting choices](deploy/cloud-overview.md).

Use PG16/17 and DATABASE_CONNECTION_MODE=direct or session with TLS. Supavisor session transport uses port 5432;
shared wire login may be ROLE.PROJECT while the SQL principal is ROLE. Transaction port 6543 is unsupported,
including runtime. Preserve CA/certificate options in dumps and dedicated locks. Qualify retained sessions with
competing locks; a stable PID alone is insufficient.

Use a non-owner NOINHERIT runtime login with classified app DML/sequence/required-function rights. Release has
finite separate maintenance credentials. Runtime must not have memberships, CREATE, TRUNCATE or trigger rights.
Probe pgcrypto/pg_trgm in their installed namespaces; do not relocate provider extensions. The forward digest
migration removes public.digest assumptions from approved application trigger functions. Portable exports need
qualified isolated scratch DBs; never drop preprovisioned operator DBs.

Free/paid accounts have different pause/cap/backup entitlements. Record actual version, backup enablement,
retention/PITR and a drill. See [free](deploy/cloud-free.md), [Render](deploy/cloud-render.md),
[Cloud Run](deploy/cloud-cloud-run.md) and [recovery](deploy/cloud-recovery.md).
[Official connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres) checked 2026-10-18;
live privilege/session/recovery acceptance is unverified.
