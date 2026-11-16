"""Query-free retained provider declaration; G installs it in shared registries."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RetainedProviders:
    attachment_capture: object
    object_keys: object
    domain_purge_preflight: object
    domain_purge_detach: object
    whole_tenant_cleanup: object
    remap_summary: object
    sweep_retention: object
    recover_work: object
    remap_eligibility: object
    remap_allocations: object
    remap_hold_refs: object
    remap_core_references: object


def providers():
    # Imports contain declarations/functions only: never ORM queries in ready().
    from .object_capture import capture, collect_keys
    from .purge import preflight_locked, detach_locked, collect_whole_tenant_locked
    from .portable import remap_summary, remap_eligibility, remap_allocations, remap_hold_refs, remap_core_references
    from .tasks import sweep_retention_task, recover_finance_work_task
    return RetainedProviders(capture, collect_keys, preflight_locked, detach_locked,
        collect_whole_tenant_locked, remap_summary, sweep_retention_task, recover_finance_work_task,
        remap_eligibility, remap_allocations, remap_hold_refs, remap_core_references)
