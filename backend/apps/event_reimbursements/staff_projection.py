"""Staff screening/finance read fields (decision 296 hackathon-flow review).

The staff console needs a person label, the amounts in play and the exact versions every finance
command checks (pool, decision sequence, obligation, attendance). These are read-only additions to
``projections``: nothing here writes, and finance-only values stay finance-only.
"""
from apps.payments.event_payouts.errors import PayoutError

REQUEST_DECIDABLE = ("requested", "waitlisted", "awarded")


def owner_label(user):
    if user is None:
        return ""
    return (getattr(user, "display_name", "") or user.get_full_name() or user.username or "").strip()[:200]


def request_extras(row, award):
    """Who asked, whether the award decision is open, and the tiers a fixed/route policy offers."""
    programme = row.programme
    decidable = row.state in REQUEST_DECIDABLE and (award is None or award.state == "offered")
    tiers = []
    if programme.award_mode in ("fixed_tier", "route_cap"):
        for key, rule in sorted((programme.tier_rules or {}).items()):
            if isinstance(rule, dict) and type(rule.get("amount_minor")) is int:
                tiers.append({"key": key, "label": str(rule.get("label") or key)[:120], "amount_minor": rule["amount_minor"]})
    return {"owner_label": owner_label(row.member), "allowed_actions": ["decide"] if decidable else [], "tiers": tiers}


def claim_extras(row, *, finance, detail):
    revision = row.current_revision
    value = {"owner_label": owner_label(row.member), "currency": row.award.currency,
             "claimed_minor": revision.total_minor if revision else 0}
    if not detail:
        return value
    award = row.award
    decision = row.current_decision
    value.update(accepted_cap_minor=award.amount_minor, pool_version=award.pool.version,
                 decision_sequence=row.decisions.count(), decision_reason=decision.reason if decision else "")
    value.update(_attendance(row))
    reviews = row.reviews.filter(revision=revision) if revision else row.reviews.none()
    value["recommendations"] = [{"recommendation": r.recommendation, "reason_code": r.reason_code, "note": r.note}
                                for r in reviews.order_by("submitted_at", "pk")]
    from .claim_decision_models import ClaimAppeal
    appeal = ClaimAppeal.objects.filter(claim=row, resolution_at__isnull=True).first() if finance else None
    value["appeal_statement"] = appeal.statement if appeal else None
    value["review_lines"] = [_line(row, line, finance) for line in (revision.lines.select_related("finance_asset")
                             .order_by("line_uuid") if revision else [])]
    return value


def _attendance(row):
    from .attendance import evidence
    from .config_models import ReimbursementProgramme
    try:
        facts = evidence(claim=row, programme=ReimbursementProgramme.objects.get(event=row.event), enforce=False)
    except (PayoutError, ReimbursementProgramme.DoesNotExist):
        return {"registration_id": None, "attendance_revision": 0, "eligibility_revision": 0, "attendance_eligible": False}
    return {"registration_id": facts["registration_id"], "attendance_revision": facts["attendance_revision"],
            "eligibility_revision": facts["attendance_revision"], "attendance_eligible": bool(facts["eligible"])}


def _line(claim, line, finance):
    from apps.payments.event_payouts.receipt_models import ReceiptUse
    from .claim_revision_models import ClaimLine
    shared = (ClaimLine.objects.filter(receipt_hash=line.receipt_hash, revision__claim__event__makerspace_id=claim.event.makerspace_id)
              .exclude(revision__claim=claim).exists())
    use = ReceiptUse.objects.filter(makerspace_id=claim.event.makerspace_id, sha256=line.receipt_hash).first()
    value = {"line_uuid": str(line.line_uuid), "category": line.category, "original_amount_minor": line.original_amount_minor,
             "original_currency": line.original_currency, "converted_minor": line.converted_minor,
             "receipt_present": bool(line.receipt_hash), "duplicate_receipt": shared,
             "receipt_use_version": use.version if use else 1}
    if finance:
        value.update(receipt_asset_id=line.finance_asset_id, vendor=line.vendor, description=line.description,
                     expense_date=line.expense_date, fx_rate=str(line.fx_rate))
    return value
