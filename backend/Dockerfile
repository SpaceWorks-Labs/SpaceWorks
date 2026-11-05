# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS application
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates age fonts-noto-core fonts-noto-extra fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app \
    && useradd --system --create-home --uid 10001 --gid app app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN python -m scripts.bundle_cjk_fonts \
    && python -m scripts.verify_printable_runtime --bundle
# Static files belong to each serving image, never a release container filesystem.
RUN DJANGO_SETTINGS_MODULE=config.settings_build python manage.py collectstatic --noinput \
    && mkdir -p /var/lib/celery /var/lib/spaceworks/ops /var/lib/spaceworks/models /run/spaceworks-host \
    && chown -R app:app /app/staticfiles /var/lib/celery /var/lib/spaceworks/ops /var/lib/spaceworks/models
EXPOSE 8000
ENTRYPOINT ["python", "/app/scripts/spaceworks_entrypoint.py"]
CMD ["--role", "backend", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

# Full-server tools (versioned Postgres clients, ffprobe), shared by both targets below.
FROM application AS server-tools
ARG POSTGRESQL_CLIENT_MAJOR=17
ARG POSTGRESQL_LOCAL_SERVER_MAJOR=16
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg age ffmpeg fonts-noto-core fonts-noto-extra fonts-dejavu-core \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
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
# tools, user, entrypoint and role command are the published image's.
FROM server-tools AS full
ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo full > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=full BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app
