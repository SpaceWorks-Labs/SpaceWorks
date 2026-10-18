"""Bounded adapters installed explicitly; no fallback to eager global sweeps."""
from .cloud_jobs.contracts import ChunkResult, install_chunk


def email_outbox(context):
    from apps.integrations.mail_providers.outbox import drain
    context.check()
    result = drain(monotonic_deadline=context.deadline, limit=context.limit,
                   guard=context.check, cursor=context.checkpoint.get("cursor", 0))
    context.check()
    return ChunkResult(not result.get("remaining", False),
                       {"cursor": result.get("cursor", 0)}, result["processed"])


def evidence_retention(context):
    from apps.evidence.services_retention import sweep_evidence_retention
    return evidence_chunk(context, sweep_evidence_retention)


def abandoned_evidence(context):
    from apps.evidence.abandoned_upload_cleanup import sweep_abandoned_evidence_uploads
    return evidence_chunk(context, sweep_abandoned_evidence_uploads)


def evidence_chunk(context, callback):
    from apps.storage_capabilities.budget import storage_budget
    context.check()
    with storage_budget(deadline=context.deadline, check_active=context.check):
        result = callback(batch_size=min(context.limit, 5), cursor=context.checkpoint or None)
    context.check()
    complete = not result.get("next_cursor") and not result.get("continuation_required", False)
    if result.get("failed", 0):
        raise RuntimeError("Evidence sweep reported an unresolved failure.")
    return ChunkResult(complete, result.get("next_cursor") or {}, result.get("deleted", 0))


def install():
    # The complete personal-envelope adapter must compose this email drain before
    # its own source-aware delivery. Do not label legacy mail alone a whole sweep.
    install_chunk("evidence-object-expiry", evidence_retention)
    install_chunk("evidence-abandoned-upload-cleanup", abandoned_evidence)
