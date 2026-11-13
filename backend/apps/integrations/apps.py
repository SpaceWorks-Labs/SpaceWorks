from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"

    def ready(self):
        from .notification_diagnostics import register as register_diagnostics
        register_diagnostics()
        from .notification_wa_meta import register_meta_provider
        register_meta_provider()
        from .notification_telegram import register_telegram_provider
        register_telegram_provider()
        from .delivery_digest import register_digest
        register_digest()
        from .notification_email_source import register_email_source
        register_email_source()
        from .notification_wa_twilio import register as register_wa_twilio
        register_wa_twilio()
        from .notification_slack import register as register_slack
        from .notification_mattermost import register as register_mattermost
        from .notification_discord import register as register_discord
        register_slack()
        register_mattermost()
        register_discord()
        # Release 2 L2 (X37): invitations offered on the invitee's own chat channels.
        from .invite_chat import register as register_invite_chat
        register_invite_chat()
