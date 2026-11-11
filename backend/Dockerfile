# syntax=docker/dockerfile:1.7
# The one place the ffmpeg version is set: both stages below re-declare it (no default) to inherit it.
ARG FFMPEG_VERSION=9.0.2
# Selects the serving base below; a global ARG must precede the first FROM to be used in `FROM`.
ARG BASE_OS=ubuntu-noble
# Build-only stages first. Nothing installed in them ships: the serving image copies
# out one verified file each, so their tooling (gettext, curl, gnupg) never reaches
# the published image or its vulnerability scan.

# Gettext catalogues: msgfmt is a build tool. Same invocation Django's
# compilemessages makes (`msgfmt --check-format`); .mo files are never committed.
FROM python:3.12-slim AS catalogues
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*
COPY locale /src/locale
RUN find /src/locale -name '*.po' -exec sh -c 'msgfmt --check-format -o "${1%.po}.mo" "$1"' _ {} \;

# PGDG archive key, fingerprint-checked here so gnupg and curl stay out of the image.
# apt accepts the ASCII-armoured key directly through signed-by.
FROM python:3.12-slim AS pgdg-key
ARG PGDG_KEY_FINGERPRINT=B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /pgdg.asc \
    && test "$(gpg --batch --with-colons --show-keys /pgdg.asc | grep -c '^pub:')" = 1 \
    && test "$(gpg --batch --with-colons --show-keys /pgdg.asc | awk -F: '/^pub:/ {getline; print $10; exit}')" = "$PGDG_KEY_FINGERPRINT"

# ffprobe, built from a pinned and checksum-verified FFmpeg source release (decision 222(b)).
# Debian's `ffmpeg` package drags in ~150 library packages (libxml2 among them) that the
# event video probe never uses. This stage compiles ONLY ffprobe, statically, with every
# component disabled except the mov and matroska demuxers, the file and pipe protocols and
# the parsers needed to name a stream's codec. No external libraries (no libxml2, no zlib),
# no network. Bump FFMPEG_VERSION and FFMPEG_SHA256 together with each release
# (docs/security/backend-image-cve-notes-0.12.0.md says how); the version is also written
# to the image LABEL spaceworks.ffmpeg.version.
FROM python:3.12-slim AS ffprobe-build
ARG FFMPEG_VERSION
ARG FFMPEG_SHA256=8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSL "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" -o ffmpeg.tar.xz \
    && echo "${FFMPEG_SHA256}  ffmpeg.tar.xz" | sha256sum -c - \
    && tar -xJf ffmpeg.tar.xz --strip-components=1 \
    && ./configure \
      --disable-everything --disable-autodetect --disable-network --disable-doc \
      --disable-debug --disable-x86asm --disable-ffmpeg --disable-ffplay \
      --disable-avdevice --disable-swscale --disable-swresample --disable-avfilter \
      --enable-ffprobe --enable-small \
      --enable-demuxer=mov,matroska \
      --enable-protocol=file,pipe \
      --enable-parser=h264,vp8,vp9,av1,aac,opus,vorbis,mpegaudio \
      --pkg-config=false --extra-ldflags=-static \
    && make -j"$(nproc)" ffprobe \
    && strip ffprobe \
    && ./ffprobe -version

# Base OS (decisions 231, 237 and the "any stable Debian-based OS" follow-up). Pick with
# `--build-arg BASE_OS=ubuntu-noble|debian-trixie|debian-forky`; the default ships.
#   ubuntu-noble  (default) Ubuntu 24.04 LTS, system Python 3.12 in a venv. Trivy has Ubuntu advisories,
#                 so the scan is real; no util-linux/perl/ncurses/libacl/systemd/sqlite HIGH rows.
#   debian-trixie Debian stable on the official Python 3.12 image. The scan shows the open Debian
#                 util-linux, perl, ncurses, libacl1, systemd and sqlite findings (no fix in stable).
#   debian-forky  Debian testing: zero known findings per the Debian tracker, but Trivy has no forky
#                 advisories (cross-check against the tracker) and testing is a moving target.
#                 libsqlite3-0 alone is pinned from sid (forky has not fixed it yet); a non-forky
#                 build never sees sid.
# See docs/security/backend-image-cve-notes-0.12.0.md.
FROM ubuntu:24.04 AS base-ubuntu-noble
FROM python:3.12-slim AS base-debian-trixie
FROM python:3.12-slim AS base-debian-forky

FROM base-${BASE_OS} AS application
ARG BASE_OS
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN set -eux; \
    keyring=/usr/share/keyrings/debian-archive-keyring.gpg; \
    python_pkgs=; \
    case "$BASE_OS" in \
      ubuntu-noble) python_pkgs="python3.12 python3.12-venv" ;; \
      debian-trixie) ;; \
      debian-forky) \
        printf 'Types: deb\nURIs: http://deb.debian.org/debian\nSuites: forky\nComponents: main\nSigned-By: %s\n' \
          "$keyring" > /etc/apt/sources.list.d/debian.sources; \
        printf 'Types: deb\nURIs: http://deb.debian.org/debian\nSuites: sid\nComponents: main\nSigned-By: %s\n' \
          "$keyring" > /etc/apt/sources.list.d/sid.sources; \
        printf 'Package: *\nPin: release n=sid\nPin-Priority: 50\n\nPackage: libsqlite3-0\nPin: release n=sid\nPin-Priority: 600\n' \
          > /etc/apt/preferences.d/sid-sqlite; \
        python_pkgs=libsqlite3-0 ;; \
      *) echo "BASE_OS must be ubuntu-noble, debian-trixie or debian-forky" >&2; exit 1 ;; \
    esac; \
    apt-get update; \
    apt-get -y --no-install-recommends full-upgrade; \
    apt-get install -y --no-install-recommends $python_pkgs ca-certificates age fonts-noto-core fonts-noto-extra fonts-dejavu-core; \
    if [ "$BASE_OS" = ubuntu-noble ]; then \
      python3.12 -m venv /opt/venv; \
      apt-get purge -y python3.12-venv python3-pip-whl; \
    fi; \
    rm -f /etc/apt/sources.list.d/sid.sources /etc/apt/preferences.d/sid-sqlite; \
    apt-get autoremove -y --purge; \
    rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app \
    && useradd --system --create-home --uid 10001 --gid app app
WORKDIR /app
COPY requirements.txt .
# The base image can ship an installer affected by CVE-2026-13346, and a setuptools below
# the 78.1.1 security fix (222(b) scan). pip is uninstalled once the requirements are in: no
# runtime or test path calls it, and its vendored copies of certifi, msgpack, urllib3 and
# setuptools 70.3.0 were the only Python findings left in the scan (decision 231).
RUN python -m pip install --no-cache-dir --upgrade pip==26.3 "setuptools>=78.1.1" \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip uninstall -y pip
COPY --chown=app:app . .
RUN python -m scripts.bundle_cjk_fonts \
    && python -m scripts.verify_printable_runtime --bundle
# Phase 8 i18n: the committed catalogues (backend/locale/*/LC_MESSAGES/django.po),
# compiled in the `catalogues` stage. The copied locale tree is root-owned (read-only to app).
COPY --from=catalogues /src/locale/ /app/locale/
# Static files belong to each serving image, never a release container filesystem.
RUN DJANGO_SETTINGS_MODULE=config.settings_build python manage.py collectstatic --noinput \
    && mkdir -p /var/lib/celery /var/lib/spaceworks/ops /var/lib/spaceworks/models /run/spaceworks-host \
    && chown -R app:app /app/staticfiles /var/lib/celery /var/lib/spaceworks/ops /var/lib/spaceworks/models
EXPOSE 8000
ENTRYPOINT ["python", "/app/scripts/spaceworks_entrypoint.py"]
CMD ["--role", "backend", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

# Full-server tools (versioned Postgres clients, ffprobe), shared by both targets below.
# ffprobe is the source-built binary from `ffprobe-build`; the event video probe needs it
# and no Debian ffmpeg/libav*/libxml2 package is installed for it.
FROM application AS server-tools
ARG FFMPEG_VERSION
LABEL spaceworks.ffmpeg.version="${FFMPEG_VERSION}"
COPY --from=ffprobe-build /build/ffprobe /usr/local/bin/ffprobe
ARG POSTGRESQL_CLIENT_MAJOR=17
ARG POSTGRESQL_LOCAL_SERVER_MAJOR=16
COPY --from=pgdg-key /pgdg.asc /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
ARG BASE_OS
RUN codename="${BASE_OS#*-}"     && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${codename}-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      "postgresql-client-$POSTGRESQL_CLIENT_MAJOR" \
      "postgresql-client-$POSTGRESQL_LOCAL_SERVER_MAJOR" \
    && rm -rf /var/lib/apt/lists/*

# The ONE published backend image, spaceworks-backend. It runs every deployment
# profile: host/full by default, or managed full/free selected at start-up by
# SPACEWORKS_DEPLOYMENT_MODE and SPACEWORKS_DEPLOYMENT_PROFILE (the common
# entrypoint hands managed mode to cloud_entrypoint). It adds only the cloud setup
# tooling, from the repository-root BuildKit named context cloud_tooling.
FROM server-tools AS release
COPY --from=cloud_tooling scripts/cloud_setup /app/scripts/cloud_setup
COPY --from=cloud_tooling scripts/init-cloud-environment.py /app/scripts/init-cloud-environment.py
COPY --from=cloud_tooling deploy /app/deploy
ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo full > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=full BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app

# Last/default target: a plain `docker build backend` source build (dev stack,
# test runner, installer --build). It needs no named context; the full-server
# tools, user, entrypoint and role command are the published image's. curl is
# here only: the test runner uses this target and the host-installer behaviour
# tests skip without it. The published `release` image never carries curl.
FROM server-tools AS full
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo full > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=full BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app
