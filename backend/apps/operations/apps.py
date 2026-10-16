from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operations"

    def ready(self):
        from apps.operations import report_coverage  # noqa: F401
        from apps.operations import report_validation  # noqa: F401
