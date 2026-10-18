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
    return active_holds(obligation, kind="retention").exists()


def publish_locked(obligation, *, evidence_revision, evidence, eligible, reason_code, actor):
    require(evidence_revision >= obligation.eligibility_revision, "eligibility_changed")
    prior = obligation.eligibility_history.filter(evidence_revision=evidence_revision).first()
    if prior:
        require(prior.evidence == evidence, "eligibility_changed")
        return prior
    status = "eligible" if eligible and not active_holds(obligation, kind="eligibility").exists() else "held"
    row = PayoutEligibility.objects.create(obligation=obligation, evidence_revision=evidence_revision,
        evidence=evidence, status=status, reason_code=reason_code)
    obligation.eligibility_status, obligation.eligibility_revision = status, evidence_revision
    obligation.eligibility_evidence = evidence
    obligation.hold_reason_code = reason_code if status == "held" else ""
    obligation.version += 1
    obligation.save()
    record(actor, "finance.event_payout.eligibility_changed", makerspace=obligation.makerspace,
        target=obligation, meta={"eligibility_revision": evidence_revision, "status": status, "reason_code": reason_code})
    return row


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
                require(row.eligibility_evidence.get("eligible") is True, "attendance_not_eligible")
        kind = prior.kind if prior else data["kind"]
        marker = PayoutHold.objects.create(obligation=row, eligibility_revision=row.eligibility_revision,
            kind=kind, action="release" if release else "hold", releases=prior, actor=ctx.actor,
            reason_code=data["reason_code"], note=data.get("note", ""), evidence_refs=data.get("evidence_refs", []),
            hold_until=data.get("hold_until"), operation_id=data["operation_id"])
        if kind == "eligibility":
            held = active_holds(row, kind=kind).exists()
            row.eligibility_status = "held" if held else "eligible"
            row.hold_reason_code = data["reason_code"] if held else ""
        row.version += 1
        row.save()
        record(ctx.actor, "finance.event_payout.held" if not release else "finance.event_payout.hold_released",
            makerspace=row.makerspace, target=marker, meta={"obligation_id": str(row.pk), "kind": kind,
                                                         "reason_code": data["reason_code"]})
        return ctx.finish(hold_id=str(marker.pk))
