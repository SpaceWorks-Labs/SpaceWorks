---
title: Container images
group: Hosting
order: 40
summary: The published backend and website images, the Ubuntu 24.04 default base, the Debian alternatives and what the vulnerability scan shows.
---

# Container images

Every release publishes two images to the GitHub container registry:

- `ghcr.io/spaceworks-labs/spaceworks-backend`
- `ghcr.io/spaceworks-labs/spaceworks-frontend`

Installs and updates pin an immutable tag of the form `X.Y.Z-main.<run>.<12-character commit>`. A fork
publishes its own images under its own owner. The same backend image runs every role (web, worker,
scheduler, live events, one-off jobs); the role is chosen when the container starts.

## The backend base operating system

The backend image is built from `backend/Dockerfile`. The base is chosen with the `BASE_OS` build argument:

| `BASE_OS` | Base | Notes |
| --- | --- | --- |
| `ubuntu-noble` (default) | Ubuntu 24.04 LTS, system Python 3.12 in a virtual environment | What ships. The vulnerability scanner has Ubuntu advisories, so the scan is meaningful. |
| `debian-trixie` | Debian stable on the official Python 3.12 image | The scan shows open Debian findings with no stable fix yet. |
| `debian-forky` | Debian testing | Fewest known findings per the Debian tracker, but the scanner has no advisories for it and testing moves. One library, `libsqlite3-0`, is pinned from Debian unstable because testing has not fixed it. |

```bash
docker build --build-arg BASE_OS=debian-trixie -t spaceworks-backend backend
```

Building your own image is only needed if you want a different base. The published images use the default.
To build from source with the compose files, use `docker/compose.build.yml` (see
[Docker Compose profiles](docker-compose.md#other-layers)).

## What is in the image

- Python 3.12 with the application dependencies; the PostgreSQL client matching the supported servers
  (16 and 17), so backups and restores use a version-matched `pg_dump`.
- A small, statically linked `ffprobe` built from a pinned, checksum-verified FFmpeg source release, used to
  check event video uploads. The image does not install Debian's full `ffmpeg` package, which removed a large
  set of libraries from the image. The version is recorded in the image label `spaceworks.ffmpeg.version`.
- Compiled translation catalogues. Build tools (gettext, the compiler for `ffprobe`, curl, gnupg) are used in
  build-only stages and do not ship.
- A non-root runtime user.

## Vulnerability scan summary

The maintainers scan the backend image with Trivy and keep per-finding notes in the repository
([backend image CVE notes](../security/backend-image-cve-notes-0.12.0.md)). In short, for the default
Ubuntu base the remaining operating-system findings are in base packages (util-linux, SQLite, ncurses, perl,
systemd libraries, libacl and the MIT Kerberos client libraries). Each has been reviewed as not reachable
with untrusted input, because the application runs as a non-root user, uses PostgreSQL rather than SQLite,
and does not run the affected server daemons. Findings that the scanner attributes to Python packages come
from the copy of pip's vendored manifest in the image, not from importable application code.

The security summary for the release records that the final image must be rebuilt and re-scanned by exact
digest, and that unfixed findings are not hidden. See the [0.12.0 security summary](../security-summary-0.12.0.md).
