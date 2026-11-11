from django.apps import AppConfig


class HardwareRequestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hardware_requests"
    label = "hardware_requests"

    def ready(self):
        from . import checks  # noqa: F401
        from .notifications_p2_requests import register
        from .notifications_p2_reminders import register as register_reminders
        from .notifications_p2_reports import register as register_reports
        register()
        register_reminders()
        register_reports()
        from . import guest_signals  # noqa: F401  (decision 223 (f): sponsor notice + incident on a new loss/damage row)
