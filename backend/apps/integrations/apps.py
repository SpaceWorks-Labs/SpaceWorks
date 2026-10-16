from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"

    def ready(self):
        from .delivery_digest import register_digest
        register_digest()
        from .notification_email_source import register_email_source
        register_email_source()
        from .notification_wa_twilio import register as register_wa_twilio
        register_wa_twilio()
