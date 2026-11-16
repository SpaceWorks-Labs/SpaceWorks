from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"

    def ready(self):
        from apps.audit import checks, control_log, signals  # noqa: F401

        control_log.install()
