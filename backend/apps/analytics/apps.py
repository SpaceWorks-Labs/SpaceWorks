from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Release 2 L25 (#163B): per-space read-only analytics logins and Metabase embedding."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Analytics"
