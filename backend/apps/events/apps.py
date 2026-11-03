from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"

    def ready(self):
        from apps.encryption.registry import register_retained_pii
        register_retained_pii("events.StageForm")
        from apps.events import station_auth  # noqa: F401
        from apps.separability.tombstones import register_separable_app

        register_separable_app("events")
        from apps.separability.tombstones import app_is_tombstoned

        if not app_is_tombstoned("events"):
            from .integration_targets import register_targets
            register_targets()
            # Release 2 L3: the event_card holder kind for the shared card engine.
            from .id_cards_holder import register as register_event_cards
            register_event_cards()
            # Release 2 L6 (#169): invites and ticket PDFs on registration confirmation emails.
            from .registration_invites import register as register_invites
            register_invites()
            from .website_adapter import register_website
            register_website()
            from .broadcasts import register_broadcasts
            from .services_bulk_invites import register_invitations
            from .report_subject import register_subject
            register_broadcasts()
            from .notification_sources import register_event_sources
            register_event_sources()
            from .programme_runtime import register_programme_runtime
            register_programme_runtime()
            register_invitations()
            register_subject()
            from apps.makerspaces.resource_grant_sources import ResourceGrantSource, register
            from .staff_payload import granted_event_entries, has_grant_authority
            from .serializers_staff_grants import GrantedEventEntrySerializer

            register(ResourceGrantSource(
                "event_grants", has_grant_authority, granted_event_entries, GrantedEventEntrySerializer,
            ))
