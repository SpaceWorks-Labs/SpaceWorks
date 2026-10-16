from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bookings"

    def ready(self):
        from apps.separability.tombstones import register_separable_app

        register_separable_app("bookings")

        from apps.separability.tombstones import app_is_tombstoned
        if not app_is_tombstoned("bookings"):
            from .integration_targets import register_targets
            register_targets()
            from .website_adapter import register_website
            register_website()
            from .report_subject import register_subject
            register_subject()
            from .broadcasts import register_broadcasts
            from .reminder_delivery import register_reminders
            register_broadcasts()
            register_reminders()
            from .notification_sources import register_notification_sources
            register_notification_sources()
            from apps.makerspaces.resource_grant_sources import ResourceGrantSource, register
            from .staff_payload import granted_booking_entries, has_grant_authority
            from .serializers_staff_grants import GrantedBookingEntrySerializer
            register(ResourceGrantSource(
                "booking_grants", has_grant_authority, granted_booking_entries, GrantedBookingEntrySerializer,
            ))
