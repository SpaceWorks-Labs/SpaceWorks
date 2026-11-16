"""Stage-only deletion inside G's authorized Events/whole-tenant purge.

Reimbursement-only purge must never delete independent staged forms. G owns
the irreversible permission and app.allow_immutable_delete transaction fence.
"""
from django.db import connection
from django.utils import timezone
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse, StageFormResponseRevision
from .upload_models import StageFormAsset, StageFileCleanup
from .milestone_models import EventStageMilestone
from .work_models import StageActivationJob, StageReconcileCursor


def preflight(*, makerspace, module_key):
    if module_key not in ("events", "event_reimbursements", "tenant"):
        raise ValueError("Unknown purge scope.")
    if module_key == "event_reimbursements":
        return {"stage_rows": "preserved"}
    missing = StageFormAsset.objects.filter(event__makerspace=makerspace).exclude(
        pk__in=StageFileCleanup.objects.values("source_asset_id")).exists()
    if missing:
        raise ValueError("Stage file cleanup locators are missing.")
    return {"stage_rows": "delete_after_locator_preservation"}


def delete_locked(*, makerspace, module_key):
    if not connection.in_atomic_block:
        raise RuntimeError("Use the authorized enclosing purge transaction.")
    preflight(makerspace=makerspace, module_key=module_key)
    if module_key == "event_reimbursements":
        return 0, frozenset()
    now = timezone.now()
    StageFileCleanup.objects.filter(tenant_id=makerspace.pk).update(not_before=now, next_attempt_at=now)
    # Break the two retained history pointers before deleting immutable children.
    StageFormAssignment.objects.filter(event__makerspace=makerspace).update(completed_response=None)
    StageFormResponse.objects.filter(event__makerspace=makerspace).update(current_submitted_revision=None)
    total, labels = 0, set()
    for model in (StageFormAsset, StageFormResponseRevision, StageFormResponse, StageFormAssignment,
                  StageActivationJob, StageReconcileCursor, EventStageMilestone, EventStageForm):
        # Response revisions reach their host through the response; every other row has an event.
        host = "response__event__makerspace" if model is StageFormResponseRevision else "event__makerspace"
        count, deleted = model._base_manager.filter(**{host: makerspace}).delete()
        total += count
        labels.update(deleted)
    # StageFileCleanup intentionally has no FK and is never deleted here.
    return total, frozenset(labels)
