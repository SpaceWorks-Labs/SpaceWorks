"""Immutable correction/hold history, used by synchronous attendance bridges."""
from django.utils import timezone
from apps.audit.services import record
from .eligibility_models import PayoutEligibility, PayoutHold
from .errors import require
from .transactions import command


def active_holds(obligation, *, kind=None):
    rows = obligation.hold_history.filter(action="hold", released_by_entry__isnull=True)
    return rows.filter(kind=kind) if kind else rows


def retention_held(obligation):
    # An explicit release is required. hold_until is a review date; workers
    # never silently release a legal/finance hold when a clock passes it.
    return active_holds(obligation, kind="retention").exists()


def publish_locked(obligation, *, evidence_revision, evidence, eligible, reason_code, actor, acknowledged=False,
                   require_acknowledgement=False):
    from .preflight import Facts
    facts = Facts.from_dict(evidence)
    require(facts.eligible == eligible, "invalid_eligibility_facts")
    require(evidence_revision >= obligation.eligibility_revision, "eligibility_changed")
    held = not eligible or active_holds(obligation, kind="eligibility").exists()
    needs_ack = require_acknowledgement or (not acknowledged and obligation.eligibility_status in (
        "held", "needs_acknowledgement"))
    status = "held" if held else "needs_acknowledgement" if needs_ack else "eligible"
    prior = obligation.eligibility_history.filter(evidence_revision=evidence_revision).first()
    if prior:
        require(prior.evidence == evidence and prior.status == status, "eligibility_changed")
        return prior
    row = PayoutEligibility.objects.create(obligation=obligation, evidence_revision=evidence_revision,
        evidence=evidence, status=status, reason_code=reason_code,
        acknowledged_by=actor if acknowledged else None, acknowledged_at=timezone.now() if acknowledged else None)
    obligation.eligibility_status, obligation.eligibility_revision = status, evidence_revision
    obligation.eligibility_evidence = evidence
    obligation.hold_reason_code = reason_code if status == "held" else ""
    obligation.version += 1
    obligation.save()
    record(actor, "finance.event_payout.eligibility_changed", makerspace=obligation.makerspace,
        target=obligation, meta={"eligibility_revision": evidence_revision, "status": status, "reason_code": reason_code})
    return row


def acknowledge(*, request, obligation_id, data):
    from .preflight import resolve_locked
    with command(request=request, obligation_id=obligation_id, data=data, action="eligibility.acknowledge") as ctx:
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        row = ctx.obligation
        require(row.state == "open" and data["eligibility_revision"] == row.eligibility_revision, "eligibility_changed")
        facts = resolve_locked(row)
        publish_locked(row, evidence_revision=row.eligibility_revision + 1,
            evidence=facts.as_dict(), eligible=facts.eligible, reason_code=data["reason_code"], actor=ctx.actor, acknowledged=True)
        # This is acknowledgement, never an attendance override. Ineligible facts
        # remain held until canonical evidence changes through its own workflow.
        return ctx.finish(eligibility_revision=row.eligibility_revision)


def hold(*, request, obligation_id, data, release=False):
    with command(request=request, obligation_id=obligation_id, data=data,
        action="eligibility.release" if release else "eligibility.hold") as ctx:
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        row = ctx.obligation
        require(data["eligibility_revision"] == row.eligibility_revision, "eligibility_changed")
        prior = None
        if release:
            prior = active_holds(row).select_for_update().get(pk=data["hold_id"])
            require(prior.eligibility_revision <= row.eligibility_revision, "eligibility_changed")
            if prior.kind == "eligibility":
                from .preflight import resolve_locked
                require(resolve_locked(row).eligible, "attendance_not_eligible")
        kind = prior.kind if prior else data["kind"]
        references = data.get("evidence_refs", [])
        require(len(references) == len(set(references)) and set(references) <= set(
            row.eligibility_history.values_list("pk", flat=True)), "invalid_hold_evidence", status=400)
        if not release:
            require(data.get("hold_until") is not None and data["hold_until"] > timezone.now(),
                    "hold_review_date_required", status=400)
        marker = PayoutHold.objects.create(obligation=row, eligibility_revision=row.eligibility_revision,
            kind=kind, action="release" if release else "hold", releases=prior, actor=ctx.actor,
            reason_code=data["reason_code"], note=data.get("note", ""), evidence_refs=data.get("evidence_refs", []),
            hold_until=data.get("hold_until"), operation_id=data["operation_id"])
        if kind == "eligibility":
            held = active_holds(row, kind=kind).exists()
            # Placing a safety hold must work even when canonical readers are
            # unavailable. Only release/acknowledgement needs positive facts.
            row.eligibility_status = "held" if held else "needs_acknowledgement"
            row.hold_reason_code = data["reason_code"] if held else ""
        row.version += 1
        row.save()
        record(ctx.actor, "finance.event_payout.held" if not release else "finance.event_payout.hold_released",
            makerspace=row.makerspace, target=marker, meta={"obligation_id": str(row.pk), "kind": kind,
                                                         "reason_code": data["reason_code"]})
        from .notices import enqueue_locked
        enqueue_locked(row, "hold_released" if release else "held")
        if release and kind == "retention":
            from .tasks import queue_retention
            queue_retention(obligation_id=row.pk)
        return ctx.finish(hold_id=str(marker.pk))


def hold_for_domain_review_locked(obligation, *, actor, operation_id, reason_code):
    """Domain review (appeal, cancellation, attendance or receipt change) pauses payment.

    Caller holds the domain parents and then this obligation's lock. Idempotent per
    operation; it appends an eligibility hold and bumps the obligation version so any
    readiness or export snapshot is stale. It never records or reverses a payout.
    """
    require(actor is not None, "hold_actor_required")
    prior = PayoutHold.objects.filter(operation_id=operation_id).first()
    if prior is not None:
        require(prior.obligation_id == obligation.pk and prior.action == "hold"
                and prior.reason_code == reason_code, "idempotency_conflict")
        return prior
    marker = PayoutHold.objects.create(obligation=obligation, eligibility_revision=obligation.eligibility_revision,
        kind="eligibility", action="hold", actor=actor, reason_code=reason_code, operation_id=operation_id)
    obligation.eligibility_status, obligation.hold_reason_code = "held", reason_code
    obligation.version += 1
    obligation.save(update_fields=["eligibility_status", "hold_reason_code", "version"])
    record(actor, "finance.event_payout.held", makerspace=obligation.makerspace, target=marker,
           meta={"obligation_id": str(obligation.pk), "kind": "eligibility", "reason_code": reason_code})
    from .notices import enqueue_locked
    enqueue_locked(obligation, "held")
    return marker
