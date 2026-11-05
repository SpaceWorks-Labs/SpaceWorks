# Install and update Space Works

The step-by-step guide to installing Space Works on your own server, keeping it updated and changing
its modules. For a plain-language walkthrough read [Setting up Space Works](setup-for-makerspaces.md);
for the production reference (environment, TLS, backups, the control plane) read the
[self-hosting guide](self-hosting.md).

## Install in one line

On a 64-bit Linux server (or macOS / Windows with Docker Desktop running), as a user with `sudo`:

```bash
curl -fsSL https://raw.githubusercontent.com/SpaceWorks-Labs/SpaceWorks/main/install.sh | bash
```

It asks every question first, shows a summary, and changes nothing until you confirm. Run the same
command again later to update or change modules. Details, requirements and options follow below.

## Full install guide

Space Works runs entirely through Docker Compose. It brings up **PostgreSQL, Redis, Silo object storage
(the maintained, S3-compatible fork of the archived MinIO), the Celery worker/beat, and database
migrations** and wires them to the app for you (the images don't bake in any addresses; the compose
file passes them in). Pick one path.

### Path 1: guided pinned install (easiest; no Git clone or local build)

One script checks the host, downloads the newest published GitHub release built from `main`,
generates all secrets, pulls its published images, and creates your first admin and makerspace.

**Before you start, you need:**

- a 64-bit (x86_64 or arm64) Linux server (Debian/Ubuntu, Fedora/RHEL/Alma/Rocky, Arch or openSUSE),
  macOS, or Windows Git Bash/WSL;
- on Linux, root or a user with `sudo`. The installer installs Docker, Docker Compose and curl after
  confirmation; curl/wget and tar must already exist. On macOS/Windows, Docker Desktop installed and
  running;
- internet access to `github.com` and `ghcr.io`, at least 8 GiB free disk, and curl (or wget) plus tar;
- a terminal. Prepare the answers below; required ports depend on your choices.

The questionnaire asks these choices in order. The curl installer selects the **repository before
downloading** that questionnaire; a source checkout asks it near the end.

1. **Hosting:** one makerspace (default), several at `/m/<slug>`, or a platform with tenant subdomains
   (platform domain required).
2. **Website:** serve it here (default), or API only with HTTPS website origin(s), such as Netlify.
3. **HTTPS:** plain HTTP for LAN/trial (default), automatic Caddy (domain/certificate email), or your
   own reverse proxy. Platforms use automatic HTTPS; API-only requires HTTPS. Own-proxy setup writes
   `spaceworks-proxy.nginx.conf` and prints DNS, Certbot, installation and reload steps.
4. **Storage:** bundled Silo (default), or external S3 endpoint/region, separate private/public
   buckets, access/secret keys, public-image base URL and PUT/POST presigning.
5. **Control-plane proxy:** website access to `/control/` (default off), allowed peer IPs/CIDRs and,
   with automatic HTTPS, an optional loopback HTTPS SSH-tunnel port. SaaS and API-only behind your
   own proxy skip this choice. See [control-plane access](PROJECT-STATUS.md#admin-control-plane-superadmin-only).
   The recommended answer is the default, **No**: the control plane is then reachable only from the
   server itself (this machine, or the SSH tunnel). Choosing **Yes** serves `/control/` on the site's own address;
   if you do, give an IP allowlist and keep MFA on. The managed-hosting limiter is never asked about
   and stays off. Every hosting shape is compared in [choose your hosting](choose-your-hosting.md).
6. **Web address:** hostname/IP if not already supplied.
7. **Organization name:** created as the owner of your makerspace.
8. **Makerspace name:** then the first tenant subdomain on a platform.
9. **MFA:** platform two-step sign-in (default yes); superadmins enroll optionally.
10. **Sign-in providers:** Google, Apple and/or GitHub, or none (default Google). Keys come later in
    the console; GitHub is member-only.
11. **Areas and follow-ups:** enable every area [y/N], or choose each in order: Inventory & lending
    [Y/n], Machines [Y/n], Events [y/N], Bookings [y/N], Membership [y/N], Online payments [y/N],
    Reports [Y/n], Chat alerts [y/N]. Each yes asks its settings immediately: loan limits/renewals,
    self-checkout/kiosk, charges/currency/request access, certification/reminder leads, event
    audience/currency, admission/vouches/application form and optional plans/renewals as applicable.
    Then organization labels [y/N], timezone [UTC], quiet hours [22:00–08:00], daily digests [y/N]
    and staff MFA [y/N] when platform MFA is on. The edition is derived from the selected areas.
    See [all follow-up questions/defaults](setup-for-makerspaces.md#area-follow-up-questions).
12. **Admin:** username, email and password (blank generates one).
13. **Stripe:** optional secret/webhook key pair only with Online payments; uses the area currency.
14. **Repository:** `SpaceWorks-Labs/SpaceWorks` or your fork, unless already selected by curl install.
15. **Runner:** automatic GitHub Actions deploys [y/N], offered on Linux with running systemd.

Enter accepts each displayed default; invalid answers are asked again. One summary shows every choice,
the services and host actions before **Proceed? [Y/n]**. Answering no leaves the install directory absent
and runs no package manager or Docker changes. Only the pinned release is downloaded into temporary
storage before confirmation. The summary explains: "migrate builds the database tables. It runs once
and stops. It's required." and "orchestration is a start-up safety check. It runs once and stops.
It's required." It shows whether the runner will be installed. Production creates your admin and
makerspace, with no demo/example data.

### One command for everyone, forks included

The installer's first question is which GitHub repository to install and update from: press Enter for
the main project, or type your fork as `owner/name`. To skip the question (for example in a script),
pass the fork up front:

```bash
curl -fsSL https://raw.githubusercontent.com/SpaceWorks-Labs/SpaceWorks/main/install.sh | bash -s -- --repo YourName/SpaceWorks
```

`SPACEWORKS_REPOSITORY=YourName/SpaceWorks` on the `bash` side of the pipe does the same. The choice is
saved in the install's `.env`, so every later update, installer re-run and the deploy runner keep
following that repository, and its images (`ghcr.io/yourname/spaceworks-*`). Before a fork can be
installed it must have published a release: run its **Continuous Release** workflow on `main` once (fork
→ Actions → enable workflows → Continuous Release → Run workflow). The installer refuses a repository
with no published release and says so. GitHub may create a fork's images as **private** packages, which
a server cannot pull: on your profile or organization → **Packages**, open `spaceworks-backend` and
`spaceworks-frontend` → **Package settings → Change visibility → Public** (once, after the first release).

### Who runs it, and where it goes

Run it as your normal user. It asks for your `sudo` password when it needs root, adds you to the
`docker` group if required, and leaves the install owned by you. `curl … | sudo bash` also works and
keeps the install (and its optional runner service) owned by root. `bash install.sh --help` prints the
checklist without changing anything.

It installs to `/opt/spaceworks`; set `SPACEWORKS_DIR` on the `bash` side of the pipe to override that
(on Windows Git Bash, use `SPACEWORKS_DIR="$HOME/SpaceWorks"`). It detects x86_64/aarch64 and the host
distribution, checks dependencies, Docker, ports, disk space and existing state, then installs missing
Linux dependencies through apt, dnf/yum, pacman or zypper. It verifies release availability before
deploying; the downloaded source and backend/frontend images are pinned to the tagged release.

It prints your URL and login when it finishes and offers automatic deployment from published GitHub
releases. Installs and updates pin `X.Y.Z-main.<run>.<12-hex sha>` images. `setup.sh` pulls published
images by default; developers can explicitly build locally with `bash setup.sh --build`.

### Running the installer again

Run the same curl command later and an existing install shows a menu. It never silently reinstalls or
reruns first-instance setup:

1. **Update to the latest release** — backs up the database, moves to the newest main release, runs
   migrations and restarts. Modules and data stay as they are.
2. **Change modules only** — turn optional modules (events, bookings, machines, membership, payments…)
   on or off without downloading a new version.
3. **Update, then change modules** — option 1 followed by option 2.
4. **Cancel** — exit without changing anything (the default).

An update rerun uses the latest main archive's updater. After the database backup it installs the
closed host runtime bundle, retaining previous files in `backups/host-config-*` and refreshing the
Compose trust records before deployment.

### Path 2: manual prebuilt-image setup

Pull the two published images and start the stack, after `cp .env.example .env` (fill in the few
values it asks for):

```bash
export MAKERSPACE_IMAGE_TAG=latest        # or pin a release, e.g. 0.5.1-main.42.a1b2c3d4e5f6
bash scripts/init-host-orchestration.sh   # one-time root-owned pointer/key/config state
scripts/spaceworks-compose.sh bundled up -d
```

With the default repository this pulls **`ghcr.io/spaceworks-labs/spaceworks-backend`** and
**`ghcr.io/spaceworks-labs/spaceworks-frontend`** and brings up the full stack automatically.

## Updating

Every merge to `main` builds a release: `.github/workflows/release.yml` publishes the Docker images and
the GitHub release. A server picks it up in one of two ways.

### Automatic deploys with GitHub Actions (recommended)

A GitHub Actions runner on your server receives a `deploy` job right after each release is published
and runs the updater locally. Nothing is pushed into your server and no port is opened for GitHub. You
need a **Linux server with systemd** and **admin access to the GitHub repository** you install from.

1. **Install the runner on the server.** Answer **yes** to *"Install a GitHub Actions runner on this
   server for automatic deploys?"* during setup, or later run, as the install owner:

   ```bash
   bash scripts/install-runner.sh
   ```

   It asks for a **registration token**. Get it on GitHub: the repository → **Settings → Actions →
   Runners → New self-hosted runner**, then copy the token shown in the `config.sh` command (it expires
   after an hour). Paste it at the prompt; it isn't echoed or saved. The script downloads GitHub's
   runner, checks it against GitHub's published checksum, registers it with the label
   `spaceworks-prod`, and runs it as a system service owned by the SpaceWorks install owner.
2. **Check the runner is online.** Settings → Actions → Runners shows it as **Idle** with the label
   `spaceworks-prod`.
3. **Turn deploys on.** Settings → **Secrets and variables → Actions → Variables → New repository
   variable**: name `SPACEWORKS_DEPLOY`, value `true`. Without it the deploy job is skipped, so a repo
   or fork with no runner never waits forever.
4. **Lock down who can reach the runner** (required; see [Runner security](#runner-security) below):
   - Settings → **Actions → General → Fork pull request workflows** → *Require approval for all
     external contributors*.
   - Protect `main` so only you can merge (Settings → Branches → `main` → restrict who can push, and
     apply the rule to administrators).
   - In an organization, put the runner in a runner group limited to this repository (and, if your plan
     offers it, to `release.yml` on `refs/heads/main`).
5. **Test it.** Merge something to `main`, or re-run the latest *Continuous Release* workflow. The run
   ends with a `deploy` job that runs on your server:

   ```bash
   bash "$SPACEWORKS_DIR/scripts/update.sh" --force --no-module-changes --version <that release>
   ```

   It takes a database backup, pulls the release, runs the orchestration check and `migrate`, waits
   for the app to report healthy, and rolls back the application images if it doesn't. Overlapping
   deploys queue rather than run together. The job log on GitHub shows each step, and the database
   backup taken before the update stays in `backups/` on the server.

To remove the runner: `bash scripts/install-runner.sh --remove` (it asks for a removal token from the
same Runners page), then delete the `SPACEWORKS_DEPLOY` variable.

### Manual updates

Run an update by hand as the install owner:

```bash
bash scripts/update.sh --force
# Or deploy an exact published main release:
bash scripts/update.sh --force --version 0.9.1-main.42.a1b2c3d4e5f6
```

The updater locks, backs up PostgreSQL to `backups/`, pulls pinned images, starts the stack through its
migration and orchestration gates, waits for readiness, records `.spaceworks-version`, and removes
successful run-once containers. A failed deployment attempts to restore the previous application images.
Forward database migrations remain applied; the backup is never restored automatically and does not
include uploaded files. See [recovery instructions](update-recovery.md).

Explicit `MAKERSPACE_BACKEND_IMAGE` / `MAKERSPACE_FRONTEND_IMAGE` values override the repository-derived
image names. Forks need their own published release, runner and `SPACEWORKS_DEPLOY=true` variable.
The installer prints the GitHub steps and preserves runner registration on reruns; use
`bash scripts/install-runner.sh` later to install or replace it, or `--remove` to remove it.
See [operator update steps](self-hosting.md#updating).

### Runner security

This repository is public. GitHub recommends self-hosted runners only for private repositories: a fork's
pull request can change workflows to target your runner. The runner controls Docker, effectively root
on this server. Require approval for **all external contributors'** workflow runs; restrict the runner
to this repository (and `release.yml` on `refs/heads/main` through a runner group where available).
Never add the self-hosted label to a `pull_request` workflow. The deploy job uses no checkout or
third-party actions. Keep runner auto-updates enabled. Read the
[required runner security settings](self-hosting.md#security) before enabling automatic deploys.

## Upgrades and module changes

Updates select the newest main release from GitHub. An interactive update reviews the live area switches
after the new release is healthy. The useful explicit forms are:

```bash
bash scripts/update.sh --force --modules                    # update, then review modules
bash scripts/update.sh --force --no-module-changes          # update images only
bash scripts/update.sh --modules-only --makerspace my-space # modules only; no release check
bash scripts/update.sh --all-modules --without=printing,payments \
  --makerspace my-space --confirm-removals
bash scripts/update.sh --all-modules --all-makerspaces      # explicit cross-tenant target
```

Modules belong to a makerspace through `Makerspace.enabled_modules`, not to the deployment as a whole.
When more than one makerspace exists, select one with `--makerspace <slug>` or deliberately target all
with `--all-makerspaces`; non-interactive updates refuse to guess. `--modules` requests the interactive
area menu, while `--modules-only`, `--areas=inventory,machines,...`, `--all-modules`, `--without=a,b`,
`--confirm-removals` and `--no-module-changes` support explicit operator and automation flows.

Turning an area off hides its surfaces and calls `uninstall_module`; it does **not** delete rows.
`purge_module_data` is a separate destructive command and is never called by setup or update. See
[Choosing modules](choosing-modules.md) for the areas, the per-module commands and purging.

## Object storage: MinIO is archived, Space Works now uses Silo

The MinIO server project has been archived and no longer receives releases or security fixes, so from
**0.9.0** Space Works stores evidence photos, images and documents in
[**Silo**](https://github.com/pgsty/silo) (`pgsty/silo`) instead — the maintained community fork of
MinIO. It speaks the same S3 API and keeps MinIO's `MINIO_*` settings, ports (9000 API, 9001 console)
and on-disk format, so nothing changes in your `.env`.

- **Existing installs switch automatically** on their next update. Silo reads the existing
  `minio_data` volume as-is: buckets, object versions, versioning and public-read settings carry over
  with no migration step. The Compose service and volume keep the name `minio` on purpose, so endpoint
  URLs such as `http://minio:9000` stay valid.
- **Back up `minio_data` before that first update** (see the [self-hosting guide](self-hosting.md#backups)).
  Silo does not guarantee a rollback to MinIO once it has written to the volume.
- The image is pinned with `SILO_IMAGE_TAG`; the old `MINIO_IMAGE_TAG` and `MC_IMAGE_TAG` settings are
  no longer used and can be removed from `.env`.
- Silo is licensed AGPL-3.0, the same as MinIO.

## Windows support boundary

- **Tier 1 — native:** install, run and upgrade with Docker Desktop plus Git Bash (or run the bash scripts
  inside WSL). Because native Git Bash normally has no `flock`, the updater falls back to a PID/timestamp
  directory lock, automatically clears a dead owner's lock, and provides `--override-lock` for a verified
  wedged or unreadable owner.
- **Tier 2 — WSL2 required:** in-place restore, backup import and compound host orchestration. Those
  supervisors depend on Linux AF_UNIX sockets and root-owned-file trust semantics with no native Windows
  equivalent; this tier does not have native parity.
