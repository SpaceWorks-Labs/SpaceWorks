# Koyeb

Read [hosting contracts](cloud-overview.md), [environment/setup](cloud-environment.md) and
[recovery](cloud-recovery.md). Recipe inputs: `deploy/koyeb/`. Verify the selected plan supports each resident process or finite job. Do not replace a worker with work in an HTTP response.

1. Provision PostgreSQL 16/17 direct/session transport, required extensions and a narrow runtime login.
   Provision independent private/public-final object buckets, actual capability facts and a verified email sender.
2. Render protected configuration with the wizard. Every role, full or free, uses the same immutable
   spaceworks-backend digest; the profile is chosen at start-up by SPACEWORKS_DEPLOYMENT_MODE/PROFILE.
   Replace example zero digests only with qualified builds.
3. Run the fixed release role with finite maintenance credentials before traffic. Verify DB identity, app-only
   grants, recovery state, migrations, encryption and real native storage proofs. Residents get runtime credentials only.
4. Full Redis needs web/worker/one elected beat. Full brokerless needs web/worker/scheduler <=60 seconds.
   Optional SSE uses a separate live process; otherwise use polling. [Free](cloud-free.md) has its own topology.
5. Configure exact origins, ingress, proxy count, health checks and restart policy. Verify actual mail receipt,
   uploads/privacy, domain workflows, task progress and recovery refusals. YAML rendering alone is insufficient.
6. Upgrade through the provider using an immutable build. Image rollback leaves forward migrations applied.
   Before uninstall, stop jobs/services and delete only explicitly named/tagged resources; retain required custody,
   finance/deletion records, escrow and independent recovery artifacts.

Recovery record for this installation: database plan/backups/PITR = UNVERIFIED; object retention/recovery =
UNVERIFIED; offline rebuild and same-artifact portable dump drill = NOT RUN. Follow [the runbook](cloud-recovery.md)
into a new non-routable deployment and attach DB/object/decryption evidence. Ordinary archives cannot be restored.
Signup, provider schema/CLI validation and live acceptance remain required; this guide claims no price or SLA.
[Provider reference](https://www.koyeb.com/docs/) reviewed 2026-10-18; recheck before provisioning.

## New in 0.12.0

See [the 0.12.0 settings](cloud-environment.md#new-settings-in-0120) and [choose your hosting](../choose-your-hosting.md). The rendered role environment now carries every non-secret 0.12.0 setting at its default; keep `TURNSTILE_SECRET_KEY` and `WEB_PUSH_VAPID_PRIVATE_KEY` as Koyeb secrets, set only when you turn those features on.
