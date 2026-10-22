"""Lazy imports: inactive profiles never load another lane's runtime code."""

from importlib import import_module

from django.core.exceptions import ImproperlyConfigured


def dependency(module_name, attribute):
    try:
        module = import_module(module_name)
        return getattr(module, attribute)
    except (ImportError, AttributeError) as exc:
        # Never silently run with weaker admission/storage/delivery guarantees.
        raise ImproperlyConfigured(
            f"Cloud integration requires {module_name}.{attribute}; install the reviewed lane implementation."
        ) from exc


def managed_database(database, env):
    configure = dependency("config.cloud_database.django", "managed_database_configuration")
    import os
    tls = {name: env(name, default="") for name in (
        "PGSSLMODE", "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY", "PGSSLCRL", "PGCHANNELBINDING",
    )}
    configured = configure(env("DATABASE_URL"), environ={**os.environ, **tls})
    configured.update({k: database[k] for k in ("CONN_MAX_AGE", "CONN_HEALTH_CHECKS", "DISABLE_SERVER_SIDE_CURSORS")})
    return configured


def cloud_task_modules(*, programmes=(), tombstones=()):
    catalog = dependency("apps.operations.cloud_jobs.catalog", "periodic_catalog")
    return tuple(sorted({task.path.rpartition(".")[0] for task in catalog(programmes=programmes, tombstones=tombstones)}))


def provider_email(env):
    # E selects the transport per message; Django EMAIL_BACKEND remains the legacy fallback.
    return {"EMAIL_PROVIDER_CONFIG_FILE": env("EMAIL_PROVIDER_CONFIG_FILE", default=""),
            "EMAIL_PROVIDER_WEBHOOKS_ENABLED": env.bool("EMAIL_PROVIDER_WEBHOOKS_ENABLED", default=False)}
