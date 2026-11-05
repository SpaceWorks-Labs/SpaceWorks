"""Bounded, recoverable deadline sweeps. No storage/network I/O under row locks."""
import logging
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event, EventSeries
from apps.events.programme_locks import fences
from apps.events.tasks_sweeps import batch
from apps.operations.cloud_jobs import bounded
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.servability import servable_q
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .award_models import GrantAward
from .claim_models import ReimbursementClaim, ReimbursementWorkItem
from .transactions import Context, changed, prepared_boundary
from .claim_workflow import advance_deadlines_locked
from .request_workflow import expire_locked
from .work_items import schedule_award_locked, schedule_claim_locked

logger = logging.getLogger(__name__)


def sweep_one(*, event_id, award_id=None, request_id=None, work_id=None):
    seed = Event.objects.get(pk=event_id)
    grant_seed = GrantRequest.objects.get(pk=request_id) if request_id else GrantRequest.objects.get(award__pk=award_id)
    programme_seed = ReimbursementProgramme.objects.get(event=seed)
    accounts = tuple(sorted({grant_seed.member_id, programme_seed.approved_by_id}))
    with prepared_boundary(seed.makerspace_id), transaction.atomic(), fences(
        tenant_ids=(seed.makerspace_id,), account_ids=accounts,
    ):
        if seed.series_id:
            EventSeries.objects.select_for_update().get(pk=seed.series_id)
        event = Event.objects.select_for_update().get(pk=event_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        require_module_locked(event.makerspace, "event_reimbursements")
        programme = ReimbursementProgramme.objects.select_for_update().get(event=event)
        if not programme.enabled or programme.imported_paused:
            return False
        if programme.approved_by_id != programme_seed.approved_by_id:
            return False
        from .pools import lock_pools
        pools = lock_pools(programme)  # G14: crew awards hold the crew pool
        grant = GrantRequest.objects.select_for_update().get(pk=grant_seed.pk, programme=programme)
        award = GrantAward.objects.select_for_update().filter(request=grant).first()
        pool = pools[award.pool_id] if award else None
        claim = ReimbursementClaim.objects.select_for_update().filter(award=award).first() if award else None
        work = ReimbursementWorkItem.objects.select_for_update().filter(pk=work_id, event=event, state="pending").first() if work_id else None
        if work_id and (work is None or work.due_at > timezone.now()):
            return False
        version = claim.version if claim else award.version if award else grant.version
        operation = uuid5(NAMESPACE_URL, f"spaceworks:reimbursement-sweep:{event_id}:{grant.pk}:{version}:{work_id}")
        ctx = Context(event, programme.approved_by, {"operation_id": operation}, "",
            LockedContext(event_id=event.pk, tenant_ids=(event.makerspace_id,), account_ids=accounts), None)
        if award:
            advance_deadlines_locked(ctx, programme=programme, pool=pool, award=award, claim=claim)
        elif grant.state in ("draft", "requested", "waitlisted") and event.status == "cancelled":
            expire_locked(ctx, grant, reason_code="event_cancelled")
        if work:
            work.state = "done"
            work.save(update_fields=["state"])
        if award:
            current_claim = ReimbursementClaim.objects.filter(award=award).first()
            if award.state == "offered" or award.state == "accepted" and current_claim is None:
                schedule_award_locked(award)
            if current_claim is not None:
                due = current_claim.info_due_at if current_claim.state == "returned_for_info" else current_claim.effective_due_at
                if due > timezone.now() or current_claim.state in ("partially_approved", "rejected"):
                    schedule_claim_locked(current_claim)
        return True


@shared_task
def sweep_deadlines_task(limit=100):
    limit = batch(max(1, min(int(limit), 500)))
    spaces = servable_q("event__makerspace")
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    closed = SourceMigrationGate.objects.exclude(state="open").values("makerspace_id")
    gates = {"event__makerspace__enabled_modules__contains": ["events", "event_reimbursements"],
        "event__reimbursement_programme__enabled": True, "event__reimbursement_programme__imported_paused": False}
    # Work completion removes candidates from this queue. Unlike slicing the first
    # N events on every run, an older full page cannot starve a later event.
    work = list(ReimbursementWorkItem.objects.filter(spaces, **gates, state="pending", due_at__lte=timezone.now())
        .exclude(event__makerspace_id__in=closed)
        .order_by("due_at", "pk").values("pk", "event_id", "award_id", "claim__award_id")[:limit])
    processed = 0
    for item in bounded.items(work):
        try:
            processed += bool(sweep_one(event_id=item["event_id"], award_id=item["award_id"] or item["claim__award_id"], work_id=item["pk"]))
        except Exception:
            logger.warning("reimbursement_deadline_retry", extra={"work_id": item["pk"], "event_id": item["event_id"]})
            defer_failed_work(item["pk"])
    # Recover legacy/missed hooks and participant/event cancellation independently
    # of the due queue; never change a submitted claim for mere clock expiry.
    from django.db.models import Q, Exists, OuterRef
    pending_award = ReimbursementWorkItem.objects.filter(award_id=OuterRef("award__pk"), state="pending")
    pending_claim = ReimbursementWorkItem.objects.filter(claim_id=OuterRef("award__claim__pk"), state="pending")
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    held = EventPayoutObligation.objects.filter(source_kind="event_reimbursement",
        source_uuid=OuterRef("award__claim__uuid"), eligibility_status="held")
    candidates = GrantRequest.objects.filter(spaces, **gates).exclude(event__makerspace_id__in=closed).annotate(
        award_pending=Exists(pending_award), claim_pending=Exists(pending_claim), core_held=Exists(held)).filter(
        Q(event__status="cancelled", award__state__in=("offered", "accepted")) |
        Q(event__status="cancelled", award__state="closed", core_held=False, award__claim__current_decision__approved_total_minor__gt=0) |
        Q(event__status="cancelled", state__in=("draft", "requested", "waitlisted"), award__isnull=True) |
        Q(award__state="offered", award_pending=False) |
        Q(award__state="accepted", award__claim__isnull=True, award_pending=False) |
        Q(award__claim__state__in=("draft", "open", "partially_approved", "rejected"),
            award__claim__domain_closed_at__isnull=True, claim_pending=False) |
        (Q(award__claim__state="returned_for_info", claim_pending=False) &
            (Q(award__claim__info_due_at__gt=timezone.now()) | Q(core_held=False))))
    for row in bounded.items(candidates.order_by("updated_at", "pk").distinct()[:limit]):
        try:
            processed += bool(sweep_one(event_id=row.event_id, request_id=row.pk))
            # Seed missing future work through the same fenced workflow below.
        except Exception:
            logger.warning("reimbursement_reconciliation_retry", extra={"event_id": row.event_id, "request_id": row.pk})
            defer_failed_grant(row.pk)
    return processed


def defer_failed_work(work_id):
    """Persist bounded backoff even when a missing broker prevented preparation."""
    seed = ReimbursementWorkItem.objects.select_related("event").filter(pk=work_id).first()
    if seed is None:
        return
    try:
        with boundary_tenant_write(seed.event.makerspace_id), transaction.atomic(), fences(
            tenant_ids=(seed.event.makerspace_id,), account_ids=(),
        ):
            if seed.event.series_id:
                EventSeries.objects.select_for_update().get(pk=seed.event.series_id)
            event = Event.objects.select_for_update().get(pk=seed.event_id)
            require_module_locked(event.makerspace_id, "event_reimbursements")
            work = ReimbursementWorkItem.objects.select_for_update().filter(pk=work_id, state="pending").first()
            if work:
                work.attempts += 1
                work.due_at = timezone.now() + timedelta(minutes=min(60, 5 * 2 ** min(work.attempts, 4)))
                work.save(update_fields=["attempts", "due_at"])
    except Exception:
        logger.warning("reimbursement_retry_deferred_by_gate", extra={"work_id": work_id})


def defer_failed_grant(request_id):
    """Rotate failed legacy discovery too; broken first pages must not starve later ones."""
    seed = GrantRequest.objects.select_related("event").filter(pk=request_id).first()
    if seed is None:
        return
    try:
        with boundary_tenant_write(seed.event.makerspace_id), transaction.atomic(), fences(
            tenant_ids=(seed.event.makerspace_id,), account_ids=(seed.member_id,),
        ):
            if seed.event.series_id:
                EventSeries.objects.select_for_update().get(pk=seed.event.series_id)
            event = Event.objects.select_for_update().get(pk=seed.event_id)
            require_module_locked(event.makerspace_id, "event_reimbursements")
            # Coordination timestamp only. No PII reads, broker I/O, state change
            # or fictional decision is needed to advance the discovery cursor.
            GrantRequest.objects.filter(pk=seed.pk, event=event).update(updated_at=timezone.now())
    except Exception:
        logger.warning("reimbursement_reconciliation_deferred_by_gate", extra={"request_id": request_id})
