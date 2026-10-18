"""Query-free app registration; G owns settings, shared maps and migrations."""

from django.apps import AppConfig


class EventReimbursementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.event_reimbursements"

    def ready(self):
        from apps.separability.tombstones import register_separable_app
        register_separable_app("event_reimbursements")
