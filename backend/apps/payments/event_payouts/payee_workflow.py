"""Append routing revisions; finance inspects, owners edit, retention purges."""
from datetime import timedelta
import json
from django.conf import settings
from django.utils import timezone
from apps.audit.services import record
from .errors import require
from .payee_models import EventPayeeRevision, EventPayeeReview
from .templates import validate_details, masked_details, TEMPLATE_VERSION
from .transactions import command


def current(obligation, *, lock=False):
    rows = EventPayeeRevision.objects
    if lock:
        rows = rows.select_for_update()
    return rows.filter(obligation=obligation, state="current").first()


def projection(row):
    if row is None:
        return {"state": "payee_not_requested"}
    return {"id": str(row.pk), "version": row.version, "state": row.state, "country": row.country,
        "method": row.method, "template_key": row.template_key, "template_version": row.template_version,
        "masked_details": masked_details(json.loads(row.details), country=row.country, method=row.method)
            if row.state != "purged" else "Routing details purged",
        "verified": bool(row.verified_at), "purge_due_at": row.purge_due_at}


def put(*, request, obligation_id, data):
    enabled = tuple(tuple(item) for item in getattr(settings, "EVENT_PAYOUT_ENABLED_TEMPLATES", ()))
    details = validate_details(country=data["country"], method=data["method"], template=data["template_key"],
        version=data["template_version"], details=data["details"], enabled_templates=enabled)
    require(data["disclosure_version"] == 1, "payee_disclosure_changed", status=400)
    with command(request=request, obligation_id=obligation_id, data=data, action="payee.submit", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        obligation = ctx.obligation
        require(obligation.state == "open" and obligation.approved_minor > 0, "payee_not_requested")
        old = current(obligation, lock=True)
        require(data["expected_payee_version"] == (old.version if old else None), "stale_payee_version")
        if old:
            old.state, old.version = "superseded", old.version + 1
            # Unused superseded data has its own terminal anchor. Used revisions
            # stay with the liability until the owning obligation closes.
            if not old.entries.exists():
                old.terminal_financial_at, old.closure_reason_code = timezone.now(), "superseded_unused"
                old.purge_due_at = old.terminal_financial_at + timedelta(days=30)
            old.save()
        row = EventPayeeRevision.objects.create(obligation=obligation, owner=ctx.actor,
            country=data["country"], template_key=data["template_key"], template_version=TEMPLATE_VERSION,
            method=data["method"], details=json.dumps(details, sort_keys=True, separators=(",", ":")),
            submitted_at=timezone.now(), disclosure_version=data["disclosure_version"])
        obligation.version += 1
        obligation.save(update_fields=["version"])
        record(ctx.actor, "finance.event_payout.payee_submitted", makerspace=obligation.makerspace, target=row,
               meta={"obligation_id": str(obligation.pk), "payee_revision_id": str(row.pk)})
        return ctx.finish(payee_revision_id=str(row.pk), payee_version=row.version)


def review(*, request, obligation_id, data, verified):
    with command(request=request, obligation_id=obligation_id, data=data,
        action="payee.verify" if verified else "payee.correction") as ctx:
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        row = current(ctx.obligation, lock=True)
        require(row is not None and row.pk == data["payee_revision_id"]
                and row.version == data["expected_payee_version"], "stale_payee_version")
        require(row.details and row.submitted_at, "payee_details_required")
        require(not verified or row.method != "other" or data.get("reason_code"),
                "other_method_reason_required", status=400)
        sequence = (row.reviews.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        EventPayeeReview.objects.create(obligation=ctx.obligation, payee_revision=row, sequence=sequence,
            kind="verified" if verified else "correction_requested", actor=ctx.actor,
            reason_code=data.get("reason_code", "verified"), note=data.get("note", ""), operation_id=data["operation_id"])
        row.verified_by, row.verified_at = (ctx.actor, timezone.now()) if verified else (None, None)
        row.version += 1
        row.save()
        ctx.obligation.version += 1
        ctx.obligation.save(update_fields=["version"])
        record(ctx.actor, "finance.event_payout.payee_verified" if verified else "finance.event_payout.payee_correction",
            makerspace=ctx.obligation.makerspace, target=row, meta={"payee_revision_id": str(row.pk)})
        return ctx.finish(payee_revision_id=str(row.pk), payee_version=row.version)


def reveal(*, request, obligation_id, data, owner=False):
    require(data["purpose"] == "verify_routing", "invalid_reveal_purpose", status=400)
    with command(request=request, obligation_id=obligation_id, data=data, action="payee.reveal", owner=owner) as ctx:
        # Reauthorize and re-audit each actual release, including repeated clicks.
        ctx.cas()
        row = current(ctx.obligation, lock=True)
        require(row is not None and row.state != "purged" and row.details, "payee_details_purged", status=410)
        record(ctx.actor, "finance.event_payout.payee_revealed", makerspace=ctx.obligation.makerspace,
            target=row, meta={"obligation_id": str(ctx.obligation.pk), "payee_revision_id": str(row.pk),
                             "purpose": data["purpose"], "reason_code": data["reason_code"]})
        return {"payee_revision_id": str(row.pk), "details": json.loads(row.details)}


def close_locked(obligation, *, terminal_at, reason_code):
    for row in obligation.payee_revisions.select_for_update().exclude(state="purged").order_by("pk"):
        if row.terminal_financial_at is None:
            row.terminal_financial_at, row.closure_reason_code = terminal_at, reason_code
            row.paid_closed_at = terminal_at if reason_code == "fully_paid" else None
            row.purge_due_at = terminal_at + timedelta(days=30)
            row.version += 1
            row.save()


def purge_locked(obligation, *, row, now):
    from .eligibility_workflow import retention_held
    from .queries import paid
    require(row.obligation_id == obligation.pk, "invalid_payee_binding")
    liability = obligation.state != "cancelled" and paid(obligation) < obligation.approved_minor
    used = row.state == "current" or row.entries.exists()
    require(not (liability and used), "payee_retained_for_unpaid_obligation", status=423)
    require(not retention_held(obligation) and row.purge_due_at is not None and row.purge_due_at <= now,
            "payee_retention_active", status=423)
    row.details, row.state, row.purged_at, row.version = "", "purged", now, row.version + 1
    row.save()
    record(None, "finance.event_payout.payee_purged", makerspace=obligation.makerspace, target=row,
           meta={"payee_revision_id": str(row.pk)})
