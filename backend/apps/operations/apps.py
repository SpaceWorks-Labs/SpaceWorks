from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operations"

    def ready(self):
        from django.conf import settings
        if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed":
            from .cloud_runtime import install
            install()
            if settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free":
                from .free_runtime import install as install_free
                install_free()
        from apps.operations import report_coverage  # noqa: F401
        from .notifications_p2_alerts import register
        register()
        from .notifications_p2_reports import register as register_report_notifications
        register_report_notifications()
