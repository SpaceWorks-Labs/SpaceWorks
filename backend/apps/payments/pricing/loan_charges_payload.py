"""What the loan's Charges panel reads: every loan charge, waivers, damage/lost rows."""

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled
from apps.payments.models_pricing_rules import LoanFeeWaiver
from apps.payments.pricing.rates import PRICING_FEATURE
from apps.payments.pricing.waivers import WAIVERS_FEATURE, loan_charges

LOAN_SUBJECTS = ("loan_deposit", "loan_rental", "loan_late_fee", "loan_damage", "loan_lost")


def charge_row(payment):
    from apps.payments.subjects import subject_label

    return {"id": payment.pk, "subject_type": payment.subject_type, "subject_id": payment.subject_id,
            "label": subject_label(payment, {}), "amount": payment.amount, "currency": payment.currency,
            "status": payment.status, "created_at": payment.created_at}


def loan_charges_payload(loan, actor):
    from apps.hardware_requests.loan_charges_common import loans_enabled
    from apps.hardware_requests.loan_payments import return_evidence_id, suggestion
    from apps.hardware_requests.models import RequesterAccountability
    from apps.payments.pricing.resolver import rate_card

    from apps.audit.models import AuditLog

    payments = sorted(loan_charges(loan, LOAN_SUBJECTS), key=lambda row: (row.created_at, row.pk))
    declined = set(AuditLog.objects.filter(
        makerspace_id=loan.makerspace_id, action="loan.accountability_not_charged",
        target_type="hardware_requests.hardwarerequest", target_id=str(loan.pk),
    ).values_list("meta__accountability_id", flat=True))
    by_row = {(row.subject_type, row.subject_id): row for row in payments}
    rows = []
    for item in RequesterAccountability.objects.filter(request=loan).select_related("request_item__product",
                                                                                    "makerspace"):
        subject = "loan_lost" if item.issue_type == "missing" else "loan_damage"
        amount, source = suggestion(item)
        payment = by_row.get((subject, item.pk))
        rows.append({"id": item.pk, "issue_type": item.issue_type, "quantity": item.quantity,
                     "item_label": item.request_item.product.name if item.request_item_id else None,
                     "has_return_photo": return_evidence_id(item) is not None,
                     "suggested_amount": amount, "suggested_source": source,
                     "charge": charge_row(payment) if payment else None,
                     "no_charge_decided": payment is None and item.pk in declined})
    waivers_on = feature_enabled(loan.makerspace, WAIVERS_FEATURE)
    waivers = LoanFeeWaiver.objects.filter(request=loan).select_related("created_by") if waivers_on else []
    return {
        "request_id": loan.pk, "currency": rate_card(loan.makerspace, "loans").currency,
        "pricing_enabled": feature_enabled(loan.makerspace, PRICING_FEATURE),
        "charges_enabled": loans_enabled(loan.makerspace),
        "waivers_enabled": waivers_on,
        "can_waive": waivers_on and rbac.can(actor, rbac.Action.RETURN_REQUEST, loan.makerspace_id),
        "charges": [charge_row(payment) for payment in payments], "waivers": list(waivers),
        "accountability": rows,
    }
