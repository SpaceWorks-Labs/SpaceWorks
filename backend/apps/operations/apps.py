from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operations"

    def ready(self):
        from apps.operations import report_coverage  # noqa: F401
        from .notifications_p2_alerts import register
        register()
        from .notifications_p2_reports import register as register_report_notifications
        register_report_notifications()
        from apps.operations import report_validation  # noqa: F401
