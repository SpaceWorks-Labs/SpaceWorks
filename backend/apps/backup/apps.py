from django.apps import AppConfig


class BackupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backup"

    def ready(self):
        from .space_restore_notifications import register
        register()
