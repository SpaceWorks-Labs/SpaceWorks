from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"

    def ready(self):
        from apps.separability.tombstones import register_separable_app

        register_separable_app("notifications")
        from apps.integrations.notification_builtin import register_native_push_sender
        from .member_push import send_envelope_push

        register_native_push_sender(send_envelope_push)
