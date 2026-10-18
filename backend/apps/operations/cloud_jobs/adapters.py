"""Explicit catalogue adapters; domain discoveries use bounded.page/check."""
from . import bounded
from .catalog import periodic_catalog
from .contracts import chunk_for, install_chunk


def _callback(task):
    def chunk(context):
        return bounded.invoke(context, task.resolve())
    return chunk


def install():
    # Evidence and the unified mail drain have specialised transport/cursor logic.
    specialised = {"evidence-object-expiry", "evidence-abandoned-upload-cleanup",
                   "notification-contract-outbox", "cloud-storage-qualification", "cloud-storage-usage",
                   "cloud-private-staging-cleanup", "finalize-report-rollups", "reminder-sweep"}
    from functools import partial
    from .work import WORK
    from .work_adapters import execute
    for work in WORK:
        key = "persisted-" + work.key
        specialised.add(key)
        if chunk_for(key) is None:
            install_chunk(key, partial(_work_chunk, work.key))
    for task in periodic_catalog():
        if task.free_policy != "disabled_in_free_profile" and task.key not in specialised:
            if chunk_for(task.key) is None:
                install_chunk(task.key, _callback(task))
    from apps.integrations.mail_providers.chunks import drain_chunk
    install_chunk("notification-contract-outbox", drain_chunk)
    from apps.operations.cloud_quotas.sampling import sample_storage_chunk
    install_chunk("cloud-storage-usage", sample_storage_chunk)
    from .rollups import chunk as rollup_chunk
    install_chunk("finalize-report-rollups", rollup_chunk)
    from .reminders import chunk as reminder_chunk
    install_chunk("reminder-sweep", reminder_chunk)


def _work_chunk(key, context):
    from .work_adapters import execute
    return execute(key, limit=1, fence=context.check, context=context)
