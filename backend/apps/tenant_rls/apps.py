from django.apps import AppConfig


class TenantRlsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant_rls"
    verbose_name = "Row-level security"

    def ready(self):
        from django.db.backends.signals import connection_created
        from django.db.models.signals import post_migrate

        from . import checks  # noqa: F401 - registers the guards
        from .sync import post_migrate_sync
        from .wrapper import install

        connection_created.connect(install, dispatch_uid="tenant_rls_install_wrapper")
        post_migrate.connect(post_migrate_sync, sender=self, dispatch_uid="tenant_rls_post_migrate_sync")
        try:
            from celery.signals import task_postrun, task_prerun
        except ImportError:
            return
        from .boundary import on_task_postrun, on_task_prerun
        task_prerun.connect(on_task_prerun, weak=False, dispatch_uid="tenant_rls_task_prerun")
        task_postrun.connect(on_task_postrun, weak=False, dispatch_uid="tenant_rls_task_postrun")
