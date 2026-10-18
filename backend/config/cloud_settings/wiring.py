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
    configure = dependency("config.cloud_database", "configure_database")
    return configure(database=database, env=env)


def cloud_task_modules():
    modules = dependency("apps.operations.cloud_jobs.discovery", "task_modules")
    return tuple(modules())


def provider_email(env):
    configure = dependency("apps.integrations.mail_providers.settings", "email_settings")
    return configure(env=env)
