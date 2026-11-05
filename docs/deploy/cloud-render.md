# Render

Read [hosting contracts](cloud-overview.md), [environment/setup](cloud-environment.md) and
[recovery](cloud-recovery.md). Recipe inputs: `render.yaml; deploy/render.managed.yaml; deploy/render.brokerless.yaml; deploy/render.free.yaml`. Select paid always-on services for full. The additional free blueprint uses one web service and an external tick; measure actual cold start and timeout bounds.

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
[Provider reference](https://render.com/docs/free) reviewed 2026-10-18; recheck before provisioning.

## Release 2 (0.11.0)

See [the release-2 settings](cloud-environment.md#release-2-0110-settings) and [choose your hosting](../choose-your-hosting.md). The blueprints (`render.yaml`, `deploy/render.managed.yaml`, `deploy/render.brokerless.yaml`, `deploy/render.free.yaml`) list every non-secret release-2 setting at its safe default, including `WHATSAPP_META_GRAPH_VERSION` and the `NOTIFICATION_*` keys. Add `TURNSTILE_SECRET_KEY` and `WEB_PUSH_VAPID_PRIVATE_KEY` to the environment group yourself only when you turn Turnstile or browser alerts on; Render would otherwise prompt for them at blueprint creation.
