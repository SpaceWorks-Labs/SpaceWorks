from django.apps import AppConfig
from django.db.models.signals import post_delete, post_migrate, pre_migrate


class AnalyticsConfig(AppConfig):
    """Release 2 L25 (#163B): per-space read-only analytics logins and Metabase embedding.

    The curated views are derived database objects: dropped before a migrate that changes
    the schema (a view would otherwise block an ALTER of a column it reads) and rebuilt
    after every migrate, like L8's policies. Neither step can fail a migrate. Deleting a
    connection row (a module purge or a space purge) drops its login after commit.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Analytics"

    def ready(self):
        from .db_sync import post_migrate_sync, pre_migrate_drop
        from .signals import drop_login_after_delete

        pre_migrate.connect(pre_migrate_drop, sender=self, dispatch_uid="analytics-pre-migrate")
        post_migrate.connect(post_migrate_sync, sender=self, dispatch_uid="analytics-post-migrate")
        for model in (self.get_model("AnalyticsConnection"), self.get_model("PlatformAnalyticsConnection")):
            post_delete.connect(drop_login_after_delete, sender=model, dispatch_uid=f"analytics-drop-{model.__name__}")
