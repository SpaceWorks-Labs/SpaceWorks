# Generic Docker

Read [hosting contracts](cloud-overview.md), [environment/setup](cloud-environment.md) and
[recovery](cloud-recovery.md). Recipe inputs: `docker-compose.managed.yml; docker-compose.managed-brokerless.yml; docker-compose.free.yml`. These managed files are standalone. Never layer them over the host/H1 Compose chain. Select immutable same-build digests.

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
[Provider reference](https://docs.docker.com/build/building/context/) reviewed 2026-10-18; recheck before provisioning.



Build from the repository root:
`docker buildx build --target release --build-context cloud_tooling=. -f backend/Dockerfile backend`.
That is the published spaceworks-backend image; it runs host/full, managed/full and managed/free.
Plain `docker build backend` builds the default full target for host installs, without the cloud tooling.
Such a source-built image cannot run managed mode; managed deployments use the published image.
Both install versioned clients 16/17 and ffprobe. Runtime/arm64/static checks must
pass before publication; source metadata alone is not evidence. Client-major build arguments stay explicit.

## New in 0.12.0

See [the 0.12.0 settings](cloud-environment.md#new-settings-in-0120) and [choose your hosting](../choose-your-hosting.md). `docker-compose.managed.yml` now passes the earlier settings block and the 0.12.0 settings (Turnstile, login IP block, breach check, passkey name, VAPID, messaging webhook base URL, native app minimums, card fonts) through to every role, each at its settings default. `docker-compose.managed-brokerless.yml` and `docker-compose.free.yml` read the protected runtime env file whole, so any key you put there reaches the backend.
