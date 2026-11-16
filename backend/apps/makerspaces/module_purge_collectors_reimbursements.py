"""Reimbursement and stage-form rows inside the two module purges that can reach them.

Both purges run the shared preflight first (``purge_preflight``); the delete steps here
re-check it under the purge transaction. Core payout rows, finance attachments and the
FK-free cleanup locators are never deleted: obligations are detached by the domain purge
and keep their retention anchors, and stage bytes are deleted later by the retained
locator worker, which survives the rows that named them.
"""
from django.core.exceptions import ValidationError

from .module_purge_collectors_single_model import _cascade_model_labels, _counts

REIMBURSEMENT_PII_LABELS = (
    "event_reimbursements.GrantRequest", "event_reimbursements.GrantAward",
    "event_reimbursements.ReimbursementClaim", "event_reimbursements.ClaimLine",
    "event_reimbursements.ClaimDecision", "event_reimbursements.ClaimLineDecision",
    "event_reimbursements.ClaimAppeal", "event_reimbursements.ClaimScreeningReview",
    "event_reimbursements.ClaimAttendanceAttestation",
)
STAGE_PII_LABELS = (
    "events.StageFormAssignment", "events.StageFormResponse", "events.StageFormResponseRevision",
    "events.StageFormAsset",
)


def finance_key_context(makerspace, key):
    """Prepared outside the purge transaction: the preflight reads mandatory finance
    envelopes, whose key is never refilled under row locks. No active key means no
    envelope exists, and none is created here."""
    from contextlib import nullcontext
    if key not in ("events", "event_reimbursements"):
        return nullcontext()
    from apps.encryption.models import MakerspaceEncryptionKey
    from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
    if not MakerspaceEncryptionKey.objects.filter(makerspace_id=makerspace.pk, status="active").exists():
        return nullcontext()
    return tenant_key_context(prepare_tenant_key(makerspace.pk, create=False))


def purge_preflight(makerspace, key):
    """IDs/counts only; raise before any key collection or row deletion when refused."""
    if key not in ("events", "event_reimbursements"):
        return None
    from apps.event_reimbursements.purge import preflight
    result = preflight(makerspace.pk)
    if not result["allowed"]:
        codes = {row["code"] for row in result["blockers"]}
        code = ("unfinished_reimbursements" if codes & {"unfinished_reimbursement_awards",
                "unfinished_reimbursement_claims"} else sorted(codes)[0])
        raise ValidationError({"code": code, "blockers": result["blockers"]})
    if key == "events":
        from apps.events.staged_forms.purge import preflight as stage_preflight
        try:
            stage_preflight(makerspace=makerspace, module_key="events")
        except ValueError as exc:
            raise ValidationError({"code": "missing_stage_cleanup_locator"}) from exc
    return result


def _reimbursement_rows(makerspace, cursor):
    from apps.event_reimbursements.models import ReimbursementProgramme
    from apps.event_reimbursements.purge import delete
    labels = _cascade_model_labels(ReimbursementProgramme)
    if not ReimbursementProgramme.objects.filter(event__makerspace=makerspace).exists():
        return 0, labels
    count, deleted = delete(makerspace, cursor)
    return count, labels | frozenset(deleted)


def reimbursement_delete(makerspace, cursor):
    """The reimbursement module purge: travel-support history only; stages stay."""
    count, labels = _reimbursement_rows(makerspace, cursor)
    return _counts(model_labels=labels, reimbursement_rows=count)


def events_reimbursement_and_stage_delete(makerspace, cursor):
    """First step of the Events purge, before any Event-graph row is deleted."""
    from apps.events.staged_forms.purge import delete_locked
    reimbursements, labels = _reimbursement_rows(makerspace, cursor)
    stages, stage_labels = delete_locked(makerspace=makerspace, module_key="events")
    return _counts(model_labels=labels | stage_labels, reimbursement_rows=reimbursements,
                   event_stage_rows=stages)


def preflight_report(makerspace, key):
    """Read-only summary shown before a purge is confirmed. Blockers are reported, not raised."""
    report = {"module": key, "allowed": True, "blockers": []}
    if key not in ("events", "event_reimbursements"):
        return report
    from apps.event_reimbursements.purge import preflight
    report.update(preflight(makerspace.pk))
    if key == "events":
        from apps.events.staged_forms.purge import preflight as stage_preflight
        try:
            report.update(stage_preflight(makerspace=makerspace, module_key="events"))
        except ValueError:
            report["allowed"] = False
            report["blockers"] = [*report["blockers"], {"code": "missing_stage_cleanup_locator", "count": 1}]
    return report
