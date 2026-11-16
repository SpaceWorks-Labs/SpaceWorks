"""Bulk per-page context for the L5 fields on member and staff payment rows.

Resolved once per page (a handful of queries regardless of length), never per row.
"""

from apps.payments.models import (
    MakerspaceBillingSettings, PaymentCaptureFlag, PaymentClaim, PaymentDispute, SettlementConfirmation,
)
from apps.payments.upi import upi_details


def staff_row_context(rows):
    ids = [row.pk for row in rows]
    awaiting = dict(SettlementConfirmation.objects.filter(
        payment_id__in=ids, status=SettlementConfirmation.Status.AWAITING).values_list("payment_id", "pk"))
    claims = dict(PaymentClaim.objects.filter(
        payment_id__in=ids, status__in=PaymentClaim.OPEN_STATUSES).values_list("payment_id", "pk"))
    flags = {}
    for payment_id in PaymentCaptureFlag.objects.filter(payment_id__in=ids, resolution="").values_list(
            "payment_id", flat=True):
        flags[payment_id] = flags.get(payment_id, 0) + 1
    disputed = set(PaymentDispute.objects.filter(payment_id__in=ids, status__in=("open", "under_review"))
                   .values_list("payment_id", flat=True))
    from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids

    spaces = {row.makerspace_id for row in rows}
    links = set(feature_enabled_servable_ids(spaces, "billing.pay_links")) if spaces else set()
    return {"awaiting": awaiting, "claims": claims, "flags": flags, "disputed": disputed, "pay_links": links}


def staff_flags(payment, context=None):
    context = context if context is not None else staff_row_context([payment])
    return {"method_label": payment.method_label, "awaiting_confirmation_id": context["awaiting"].get(payment.pk),
            "open_claim_id": context["claims"].get(payment.pk), "open_flags": context["flags"].get(payment.pk, 0),
            "disputed": payment.pk in context["disputed"], "taxed": bool(payment.tax_snapshot),
            "pay_link_available": (payment.member_id is None and payment.status == "pending"
                                   and payment.makerspace_id in context["pay_links"])}


def member_offline_context(rows, viewer=None):
    """Per page: billing policies, which spaces run `billing.offline_claims`, latest claims.

    With `viewer` (the signed-in member reading their OWN charges) the unit-specific instructions are resolved
    too (`unit_instructions.py`); without one the space-wide text is all anyone gets.
    """
    from apps.payments.unit_instructions import resolve_unit_instructions

    from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids

    spaces = {row.makerspace_id for row in rows}
    policies = {policy.makerspace_id: policy for policy in MakerspaceBillingSettings.objects.filter(
        makerspace_id__in=spaces)}
    latest = {}
    for claim in PaymentClaim.objects.filter(payment_id__in=[row.pk for row in rows]).order_by("-created_at", "-pk"):
        latest.setdefault(claim.payment_id, claim)
    enabled = set(feature_enabled_servable_ids(spaces, "billing.offline_claims")) if spaces else set()
    return {"policies": policies, "claims": latest, "enabled": enabled,
            "unit_instructions": resolve_unit_instructions(rows, viewer)}


def offline_collection(payment, context=None):
    from apps.payments.serializers_l5 import OwnClaimSerializer

    context = context if context is not None else member_offline_context([payment])
    policy = context["policies"].get(payment.makerspace_id)
    claim = context["claims"].get(payment.pk)
    open_claim = claim is not None and claim.status in PaymentClaim.OPEN_STATUSES
    enabled = payment.makerspace_id in context["enabled"]
    unit = context.get("unit_instructions", {}).get(payment.pk)
    # A unit with its own instructions replaces the space's UPI QR as well: the QR is the space's VPA.
    return {"upi": upi_details(payment, policy) if enabled and unit is None else None,
            "instructions": unit["text"] if unit else (policy.payment_instructions if policy else ""),
            "instructions_unit": unit["unit"] if unit else None,
            "claim": OwnClaimSerializer(claim).data if claim else None,
            "claimable": enabled and payment.status == "pending" and not open_claim}
