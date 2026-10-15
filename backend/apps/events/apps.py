from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"

    def ready(self):
        from apps.events import station_auth  # noqa: F401
        from apps.separability.tombstones import register_separable_app

        register_separable_app("events")
        from apps.separability.tombstones import app_is_tombstoned

        if not app_is_tombstoned("events"):
            from .integration_targets import register_targets
            register_targets()
            from .broadcasts import register_broadcasts
            from .services_bulk_invites import register_invitations
            from .report_subject import register_subject
            register_broadcasts()
            register_invitations()
            register_subject()
            from apps.makerspaces.resource_grant_sources import ResourceGrantSource, register
            from .staff_payload import granted_event_entries, has_grant_authority
            from .serializers_staff_grants import GrantedEventEntrySerializer

            register(ResourceGrantSource(
                "event_grants", has_grant_authority, granted_event_entries, GrantedEventEntrySerializer,
            ))
