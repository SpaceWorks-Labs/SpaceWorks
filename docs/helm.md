# Helm deployment

`charts/spaceworks` is an additional deployment manifest; it does not replace or modify the installer.
It runs backend, dedicated live/SSE, worker, beat and frontend deployments, a pre-install/pre-upgrade
migration hook, internal services and an optional frontend ingress. Use one release per namespace:
services are named `backend`, `live` and `frontend` to match the existing frontend upstream contract.
Pin the same released image tag for backend/frontend. PostgreSQL, Redis and S3 are external services.

## Operator prerequisites

This chart deliberately cannot bootstrap H1, invent a normal marker or bypass the image entrypoint.
An operator must first provision the database owner/runtime-role grant split, initialized database
identity, root-owned H1 marker, verification key and durable topology control plane described in
`docs/INVARIANTS.md` under Container / deployment invariants. Every Django process keeps the image
ENTRYPOINT and an explicit role. The migration hook uses role `migrate`; backend/live use `backend`;
Celery uses `worker`/`beat`. A missing, malformed or mismatched marker refuses startup.

Prepare these external resources before installation:

- An operator-managed read-only PVC (`hostGate.existingClaim`) with the host-state directory containing
  `restore-marker.json` and required verification material. It must remain root-owned and must not have
  a writable application alias. Use a storage driver supporting the required shared read-only mounts.
  The chart deliberately sets no fsGroup, which could make that root-owned gate group-writable.
  Keep marker mode 0444 and directory mode 0555 (or equivalent root-only-write permissions).
- A `beat.existingClaim` PVC when beat is enabled, with its directory owned/writable by uid 10001;
  scheduler state persists across replacement pods. Other writable volumes must admit uid 10001.
- A `runtimeSecret` containing Django/encryption keys and Redis/S3/deployment configuration, including
  explicit `TRUSTED_PROXY_COUNT`, allowed hosts, TLS/proxy and browser-facing storage settings. Never
  give the app database ownership/superuser credentials. Configure `METRICS_TOKEN` here if scraping.
- Two **immutable, versioned Secrets**, each holding `DATABASE_URL` and
  `SPACEWORKS_DB_POINTER_GENERATION` together: `databasePointerSecret` with runtime credentials and
  `migrationPointerSecret` with maintenance credentials to the exact same live database/generation.
  New generations use new secret names; do not patch only one key or mutate a mounted secret in place.
- `rolloutGeneration` matching that operator-committed generation. Declare and fence every writer
  (including the migration hook and any external scheduler) in the external topology before cutover.

Example rendering with existing, already-prepared resources:

```sh
helm lint charts/spaceworks --set imageTag=YOUR_RELEASE --set runtimeSecret=spaceworks-runtime \
  --set databasePointerSecret=pointer-runtime-g1 --set migrationPointerSecret=pointer-maintenance-g1 \
  --set hostGate.existingClaim=spaceworks-host-gate --set beat.existingClaim=spaceworks-beat --set rolloutGeneration=1
helm template spaceworks charts/spaceworks -f YOUR_PRIVATE_VALUES.yaml
helm upgrade --install spaceworks charts/spaceworks -f YOUR_PRIVATE_VALUES.yaml --wait --timeout 30m
```

The hook fails without retry and blocks release rollout on migration failure. Existing writers must be
fenced by the operator when a migration/cutover requires maintenance; Helm's hook ordering does not
stop already-running writers or authorize a restore. The chart uses Recreate to avoid overlapping
generations within an individual deployment. Helm does **not** provide an atomic multi-deployment
database pointer CAS, sibling allocation, privileged host supervisor or restore adapter. Restore/cutover
is unsupported until the operator supplies and verifies those H1 orchestration contracts. Do not use
`helm rollback` to move database generations backwards or consider `helm --atomic` a database rollback.

Workers and beat default enabled. Beat has one replica and an explicit writable `--schedule` on its operator-prepared persistent PVC. If either writer is disabled, declare the alternative scheduler/topology explicitly.
Application pods run unprivileged, without service-account credentials or writable host state. The
frontend retains its existing nginx image startup contract. Ingress exposes frontend only: `/control/`
remains a private backend access surface, and `/api/v1/internal/` is denied by nginx. Configure ingress
timeouts/buffering for SSE and trust exactly the real ingress proxy count. Terminate TLS at ingress.

For optional analytics populate `frontendEnv` and matching backend runtime-secret settings described in
`docs/monitoring-and-analytics.md`. Release-2 settings (Turnstile, login IP blocking, breach check, passkey name, browser
alerts, card fonts) also go in the runtime secret and default safely when absent; Turnstile additionally
needs `frontendEnv.TURNSTILE_SITE_KEY` so nginx allows the widget. `helm lint` passes, and `helm template`
renders host, managed Redis and managed brokerless; the free profile is refused by design. Metrics use one per-pod emptyDir and the Gunicorn multi-process
hooks; use Prometheus pod/endpoint discovery rather than one randomly balanced service scrape.
The chart never stores Prometheus retention data or installs a monitoring stack.

For optional web telemetry, put the same `WEB_TELEMETRY_ALLOWED_ORIGINS` value in the backend
`runtimeSecret` and `frontendEnv`. Use a comma-separated list of specifically approved HTTPS origins;
do not use wildcard hosts, paths, query strings or credentials. The list permits destinations but
does not enable a provider or replace visitor consent. The existing `WEB_ANALYTICS_*` script and full
collector URL remain separate. The frontend image applies its CSP policy at startup.

## API-only (no website)

`--set frontend.enabled=false` drops the frontend Deployment. The ingress then has no website to route to, so it
sends `ingress.apiOnlyPaths` (default `/api`, `/embed`, `/share`, `/sitemap.xml`, `/robots.txt`, `/static`,
`/.well-known`) to the `backend` service and `/api/v1/live` to `live`. An ingress cannot deny a sub-path by
itself: add your controller's rule that returns 403 for `/api/v1/internal` and `/api/v1/metrics` (for ingress-nginx, a
`configuration-snippet` annotation in `ingress.annotations`). Host the website on a static host and set the
backend `runtimeSecret` origins as described in [choose your hosting](choose-your-hosting.md#2-api-on-your-server-website-elsewhere).
Wallet passes: the `WALLET_*_FILE` settings need a volume shared by the web and worker pods that this chart does not
create; enter the credentials in the console instead ([wallet passes](wallet-passes.md)).
