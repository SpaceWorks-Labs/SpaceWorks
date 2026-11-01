from celery import Task
from django.apps import apps

from apps.tenant_migration.gate_locks import unscoped_writer_shared_boundary
from apps.tenant_migration.gate_policy import (
    TASK_EXEMPTIONS,
    TASK_INTERNAL_PARTICIPANTS,
    TASK_TENANT_RESOLVERS,
)
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from apps.backup.capture_managers import every_row


class TenantGateTask(Task):
    """Default Celery boundary: drain before closure and refuse after closure."""

    abstract = True

    def __call__(self, *args, **kwargs):
        from apps.integrations.notification_cutover import boundary
        with boundary():
            return self._dispatch(*args, **kwargs)

    def _dispatch(self, *args, **kwargs):
        from apps.operations.cloud_runtime import managed, writer, check
        if managed():
            with writer("worker"):
                from apps.operations.cloud_jobs.full_progress import invoke
                return invoke(self.name, lambda: self._call_scoped(*args, **kwargs))
        check()
        return self._call_scoped(*args, **kwargs)

    def _call_scoped(self, *args, **kwargs):
        if self.name == "apps.operations.cloud_jobs.diagnostics.installer_roundtrip":
            import re
            if len(args) != 1 or kwargs or not isinstance(args[0], str) or not re.fullmatch(r"[0-9a-f]{32}", args[0]):
                raise ValueError("Installer diagnostic invocation is invalid.")
            # No tenant/business effect. The outer managed writer admission is
            # still mandatory; the task itself writes only a 60-second cache ack.
            return super().__call__(*args, **kwargs)
        resolver = TASK_TENANT_RESOLVERS.get(self.name)
        makerspace_id = (
            _resolve_makerspace_id(resolver, args, kwargs, task_name=self.name)
            if resolver is not None else _direct_makerspace_id(self.name, args, kwargs)
        )
        if self.name in TASK_EXEMPTIONS:
            return super().__call__(*args, **kwargs)
        if self.name in TASK_INTERNAL_PARTICIPANTS:
            return super().__call__(*args, **kwargs)
        if resolver is not None:
            if makerspace_id is None:
                return super().__call__(*args, **kwargs)
            with boundary_tenant_write(makerspace_id):
                return super().__call__(*args, **kwargs)
        with unscoped_writer_shared_boundary():
            return super().__call__(*args, **kwargs)


def _resolve_makerspace_id(resolver, args, kwargs, *, task_name=None):
    model_label, position, field = resolver
    object_id = args[position] if len(args) > position else kwargs.get("job_id")
    if object_id is None:
        object_id = kwargs.get("log_id")
    if object_id is None:
        parameter = {
            "apps.events.certificates.tasks.process_batch": "batch_id",
            "apps.events.certificates.tasks.render_one": "certificate_id",
        }.get(task_name)
        object_id = kwargs.get(parameter) if parameter else None
    if object_id is None:
        return None
    return (
        every_row(apps.get_model(model_label)).filter(pk=object_id)
        .values_list(field, flat=True)
        .first()
    )


def _direct_makerspace_id(task_name, args, kwargs):
    return kwargs.get("makerspace_id")
