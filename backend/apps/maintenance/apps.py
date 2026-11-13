from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.maintenance"

    def ready(self):
        from apps.separability.tombstones import register_separable_app

        register_separable_app("maintenance")
        # L16: the issue-report notification source (recovery re-checks live authority).
        from .repairs.notify import register

        register()
        # GAP2 M2: item and room maintenance reminders (delivery re-checks the occurrence).
        from .reminders_subjects import register as register_subject_reminders

        register_subject_reminders()
        # Decision 223: the incident register's staff notice (recovery re-checks live authority).
        from .incidents.notify import register as register_incidents

        register_incidents()
