# Hetzner and Coolify

A Hetzner Cloud VPS is an ordinary Linux server, so everything in [self-hosting](../self-hosting.md) applies.
There are two ways to run Space Works on it. Both keep the full-server contract (database, object storage,
worker, beat, live events, backups and update rollback).

## Option A: the one-line installer (recommended)

1. Create a server (Ubuntu 24.04 or Debian 12; CX22 or larger, 4 GB RAM is comfortable), add your SSH key and
   point a DNS `A` record at it. Open ports 22, 80 and 443 in the Hetzner firewall.
2. Install Docker Engine and the Compose plugin (the installer checks and tells you what is missing).
3. Run the installer and answer the questions:

```bash
curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh
```

   Pin a release with `.../releases/download/<tag>/install.sh`. Choose automatic HTTPS (Caddy). Choose **API-only**
   (`--frontend api-only`) if the website lives elsewhere, and **External S3-compatible buckets** if you want
   Cloudflare R2, Backblaze B2 or Hetzner Object Storage instead of the bundled store.
4. Optional: Hetzner Object Storage is S3-compatible; treat it as a limited store (presigned `PUT`, no Object
   Lock) and see [mix and match](mix-and-match.md#storage).
5. Add a Hetzner snapshot or backup schedule as a second layer; the application's own database and object backups
   stay the supported recovery path.

## Option B: Coolify deploying `docker-compose.prod.yml`

Coolify is a self-hosted deployment panel. Use it when you want its UI for domains, certificates and updates.
The compose files were written for the installer, which prepares host state, database pointer and operation
locks that Coolify does not create, so read this section fully before choosing it.

1. Install Coolify on a server you control (one server can host both Coolify and Space Works; allow 2 GB extra RAM).
2. Prefer the **Docker Compose (raw)** resource using [`docker-compose.managed.yml`](../../docker-compose.managed.yml)
   (Redis profile) or `docker-compose.managed-brokerless.yml`. These are standalone files for installs that use
   an external database and storage: they do not need the host state directories the installer creates.
   You supply `DATABASE_URL` (a managed or self-run PostgreSQL 16), the storage and email values and the generated
   secrets from the wizard (`provider: docker`).
3. In Coolify, set the environment variables from the wizard, add one domain to the `backend` service (port 8000)
   and let Coolify's Traefik issue the certificate. Set `TRUSTED_PROXY_COUNT=1` and `TRUST_X_FORWARDED_PROTO=true`.
4. Run the `release` service once first (Coolify "run once"), then start `backend`, `worker`, `beat`.
5. The full `docker-compose.prod.yml` chain (bundled database, bundled object store, Caddy, atomic database
   pointer, update runner) is **not** supported under Coolify; use Option A for that.

## Full or API-only

- **Full**: Option A with the website question answered; or in Coolify add the `spaceworks-frontend` image as a
  second resource on the apex domain with `/api` proxied to the backend.
- **API-only (no web container)**: Option A with `--frontend api-only` (`docker/compose.api-only.yml` parks the
  website behind an inactive profile and puts nginx `api-edge` in front of the backend and live services). For
  Coolify simply do not add the frontend resource. Host the website on a static host ([adapters](cloud-static.md))
  or serve a native app only, and set `PUBLIC_APP_BASE_URL`, CORS/CSRF/staff origins as in
  [choose your hosting](../choose-your-hosting.md#2-api-on-your-server-website-elsewhere).

Wallet pass files (`WALLET_*_FILE`) work on the installer shape (or enter credentials in the console): mount the certificate files read-only into the
backend and worker through a `docker-compose.override.yml` and set the paths in `.env`.
