from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"

    def ready(self):
        from .delivery_digest import register_digest
        register_digest()
        from .notification_email_source import register_email_source
        register_email_source()
        from .notification_slack import register as register_slack
        from .notification_mattermost import register as register_mattermost
        from .notification_discord import register as register_discord
        register_slack()
        register_mattermost()
        register_discord()
