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
    && mkdir -p /var/lib/celery /var/lib/spaceworks/ops /run/spaceworks-host \
    && chown -R app:app /app/staticfiles /var/lib/celery /var/lib/spaceworks/ops
EXPOSE 8000
ENTRYPOINT ["python", "/app/scripts/spaceworks_entrypoint.py"]
CMD ["--role", "backend", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

# cloud_tooling is the repository-root BuildKit named context. Only additional
# managed targets require it; plain `docker build backend` keeps working.
FROM application AS managed-application
ENV PYTHONPATH=/app/scripts:/app
COPY --from=cloud_tooling scripts/cloud_setup /app/scripts/cloud_setup
COPY --from=cloud_tooling scripts/init-cloud-environment.py /app/scripts/init-cloud-environment.py
COPY --from=cloud_tooling deploy /app/deploy
ENTRYPOINT ["python", "/app/scripts/cloud_entrypoint.py"]

FROM managed-application AS free
ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo free > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=free BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app

FROM managed-application AS managed
ARG POSTGRESQL_CLIENT_MAJOR=17
ARG POSTGRESQL_LOCAL_SERVER_MAJOR=16
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg age ffmpeg \
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

ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo full > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=full BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app

# Last/default target preserves full-server tools, user, role command and context.
FROM application AS full
ARG POSTGRESQL_CLIENT_MAJOR=17
ARG POSTGRESQL_LOCAL_SERVER_MAJOR=16
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg age ffmpeg \
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

ARG BUILD_GIT_SHA=unknown
ARG BUILD_GIT_DESCRIBE=unknown
RUN echo full > /app/SPACEWORKS_IMAGE_PROFILE \
    && BUILD_IMAGE_PROFILE=full BUILD_GIT_SHA="$BUILD_GIT_SHA" BUILD_GIT_DESCRIBE="$BUILD_GIT_DESCRIBE" python -m scripts.write_build_info \
    && chown app:app /app/BUILD_INFO.json
USER app
