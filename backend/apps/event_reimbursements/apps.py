"""Query-free app registration; G owns settings, shared maps and migrations."""

from django.apps import AppConfig


class EventReimbursementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.event_reimbursements"

    def ready(self):
        from apps.encryption.registry import register_retained_pii
        register_retained_pii("event_reimbursements.")
        from apps.separability.tombstones import register_separable_app
        register_separable_app("event_reimbursements")
        # Retention remains importable when the runtime is tombstoned. Shared
        # PLANS/catalogue/object-capture installation belongs to lane G.
        from .retention_registration import RETENTION_PROVIDER
        self.retention_provider = RETENTION_PROVIDER
        from apps.separability.tombstones import app_is_tombstoned
        if not app_is_tombstoned("event_reimbursements") and not app_is_tombstoned("events"):
            from apps.integrations.notification_sources import register_source
            from .notices import NOTICE_SOURCE
            register_source("event.reimbursement", NOTICE_SOURCE)
            from .queue_notices import NOTICE_SOURCE as QUEUE_SOURCE
            register_source("event.reimbursement.queue", QUEUE_SOURCE)
            from .eligibility import register_readers, canonical_project
            register_readers(project=canonical_project)
