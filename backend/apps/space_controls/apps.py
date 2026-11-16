from django.apps import AppConfig


class SpaceControlsConfig(AppConfig):
    """Superadmin controls for hosted spaces (owner decision #185): suspend, read-only,
    transfer ownership, scheduled archive/purge, onboarding, announcements, health cards.

    Core, never tombstoned: the read-only and suspension refusals are enforced by the
    source gate (``write_policy``), so removing this app would silently reopen paused spaces.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.space_controls"
    verbose_name = "Space controls"

    def ready(self):
        # #195: a job queued by a confirmed superadmin action carries the actor (re-verified on run).
        from celery.signals import before_task_publish

        from .superadmin_bypass import publish_headers

        before_task_publish.connect(publish_headers, dispatch_uid="space_controls_superadmin_bypass")
