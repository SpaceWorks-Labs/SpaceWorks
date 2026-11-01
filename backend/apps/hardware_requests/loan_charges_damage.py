"""Damage and lost charges: staff-set, one per accountability row (A5).

Staff enter the amount at return or later, prefilled with a suggestion (the item's
override, then the space default, then -- lost only -- `unit_cost x quantity`). An
amount above 0 needs the return evidence photo: the row must have been recorded by a
`ReturnEvent` whose finalized evidence is that row's photo. A kit-checklist or problem-
report row without one is refused with `return_photo_required`. Handover roles may raise
it (`return_request`). A waived loan resolves to 0 and raises nothing.

One charge per row, ever: a second attempt is 409 `charge_exists`. Fixing a wrong amount
is a staff waive of the pending charge (or a refund of a paid one), then nothing else --
the row is immutable and so is its charge.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.loan_charges_common import _existing, _get_or_create, _schedule_checkout
from apps.hardware_requests.models import HardwareRequest, RequesterAccountability
from apps.payments.models import Payment

SUBJECTS = {
    RequesterAccountability.IssueType.DAMAGED: (Payment.SubjectType.LOAN_DAMAGE, "damage", "loan.damage_charged",
                                                "damage_charged", "Damage charge"),
    RequesterAccountability.IssueType.MISSING: (Payment.SubjectType.LOAN_LOST, "lost", "loan.lost_charged",
                                                "lost_charged", "Lost item charge"),
}


def return_evidence_id(row):
    """The finalized return photo that recorded this row, or None."""
    from apps.hardware_requests.models import ReturnEvent

    if not row.evidence_photo_id:
        return None
    found = ReturnEvent.objects.filter(request_id=row.request_id, evidence_id=row.evidence_photo_id).exists()
    return row.evidence_photo_id if found else None


def suggestion(row):
    """`(amount, source)` to prefill the charge step."""
    from apps.payments.pricing.build_loans import accountability_suggestion
    from apps.payments.pricing.resolver import rate_card

    card = rate_card(row.makerspace, "loans")
    product = row.request_item.product if row.request_item_id else None
    return accountability_suggestion(card, product, row.quantity, row.issue_type)


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter an amount."})
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValidationError({"amount": "Enter an amount of 0 or more with at most two decimals."})
    return amount


def _quote(row, amount, suggested, evidence_id):
    from apps.payments.pricing.components import component
    from apps.payments.pricing.quotes import Quote, line
    from apps.payments.pricing.resolver import rate_card
    from apps.payments.pricing.waivers import apply_waivers

    subject, key, *_ = SUBJECTS[row.issue_type]
    card = rate_card(row.makerspace, "loans")
    product = row.request_item.product if row.request_item_id else None
    item = line(component("loans", key), currency=card.currency, quantity=1, unit_amount=amount,
                rate_source="staff",
                target={"type": "inventory_product", "id": product.pk, "label": product.name} if product else None,
                detail={"accountability_id": row.pk, "units": row.quantity, "evidence_id": evidence_id,
                        "suggested": str(suggested[0]), "suggested_source": suggested[1]})
    return apply_waivers(Quote(domain="loans", currency=card.currency, lines=(item,), mode=card.mode), row.request)


def _audit_charge(actor, request, row, payment, evidence_id, note):
    if row.issue_type == RequesterAccountability.IssueType.MISSING:
        audit.record(actor, "loan.lost_charged", makerspace=request.makerspace, target=request, meta={
            "request_id": request.pk, "accountability_id": row.pk, "payment_id": payment.pk,
            "amount": str(payment.amount), "evidence_id": evidence_id, "note": note,
        })
        return
    audit.record(actor, "loan.damage_charged", makerspace=request.makerspace, target=request, meta={
        "request_id": request.pk, "accountability_id": row.pk, "payment_id": payment.pk,
        "amount": str(payment.amount), "evidence_id": evidence_id, "note": note,
    })


@transaction.atomic
def charge_accountability(row, actor, *, amount, note=""):
    """Raise the damage/lost charge for one row; None when it comes to 0 (no charge or waived)."""
    from apps.payments.pricing.charging import record_free
    from apps.payments.pricing.errors import ChargeExists, PricingDisabled, ReturnPhotoRequired
    from apps.payments.pricing.rates import PRICING_FEATURE
    from apps.makerspaces.platform import feature_enabled
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(row.makerspace_id)
    request = HardwareRequest.objects.select_for_update().select_related("makerspace").get(pk=row.request_id)
    if not rbac.can(actor, rbac.Action.RETURN_REQUEST, request.makerspace_id):
        raise PermissionDenied("Charging for damage or loss needs the return permission in this space.")
    if not feature_enabled(request.makerspace, PRICING_FEATURE):
        raise PricingDisabled()
    subject, _key, _action, event, label = SUBJECTS[row.issue_type]
    existing = _existing(request, subject, row.pk)
    if existing is not None:
        raise ChargeExists(payment_id=existing.pk)
    amount = _amount(amount)
    evidence_id = return_evidence_id(row)
    if amount > 0 and evidence_id is None:
        raise ReturnPhotoRequired()
    if amount <= 0:
        # "No charge" is a staff decision too: recorded, so the row shows it was decided.
        audit.record(actor, "loan.accountability_not_charged", makerspace=request.makerspace, target=request,
                     meta={"request_id": request.pk, "accountability_id": row.pk, "note": (note or "").strip()[:300]})
        return None
    # The staff note goes to the audit entry, never the charge snapshot (no free text on money rows).
    priced = _quote(row, amount, suggestion(row), evidence_id)
    if priced.total <= 0:
        record_free(priced, actor=actor, makerspace=request.makerspace, target=request,
                    subject_type=subject, subject_id=row.pk)
        return None
    payment, created = _get_or_create(request, subject, priced, actor, f"{label} - request #{request.pk}",
                                      subject_id=row.pk)
    if created:
        _audit_charge(actor, request, row, payment, evidence_id, (note or "").strip()[:300])
        notifications.notify_loan_charge(request, event, payment)
        if payment.status == Payment.Status.PENDING:
            _schedule_checkout(payment)
    return payment
