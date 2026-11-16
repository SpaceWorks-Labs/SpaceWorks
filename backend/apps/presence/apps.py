from django.apps import AppConfig


class PresenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.presence"

    def ready(self):
        from apps.separability.tombstones import register_separable_app

        register_separable_app("presence")
        from apps.separability.tombstones import app_is_tombstoned
        if not app_is_tombstoned("presence"):
            from . import signals, notifications
            signals.register()
            notifications.register()
