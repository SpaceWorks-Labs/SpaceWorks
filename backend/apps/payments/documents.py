"""Transactional numbering and idempotent issue from settled ledger rows."""

from django.db import transaction

from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.payments.models import MakerspaceBillingSettings, ManualSettlement, Payment, PaymentDocument, Refund


@transaction.atomic
def issue_bill(payment, *, actor=None):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(payment.makerspace_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    existing = PaymentDocument.objects.filter(payment=payment, kind="bill").first()
    if existing:
        return existing
    if payment.status != Payment.Status.PENDING:
        raise ValueError("Only pending charges receive a bill.")
    return _issue(payment, kind="bill", actor=actor, money_at=payment.created_at,
                  method="", reference="", amount=payment.amount)


@transaction.atomic
def issue_receipt(payment, *, actor=None, settlement=None, received_amount=None):
    """`received_amount` is set only by a staff release of a held receipt (capture flag)."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status not in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE):
        raise ValueError("Only collected payments receive a receipt.")
    from apps.payments.capture_flags import receipt_held
    if received_amount is None and receipt_held(payment):
        # Held until a staff member decides; see `capture_flags.resolve_flag`.
        return None
    if payment.status == Payment.Status.PAID_OFFLINE:
        settlement = settlement or ManualSettlement.effective_for(payment)
        if settlement is None or settlement.payment_id != payment.pk:
            raise ValueError("Offline receipt requires a settlement on this payment.")
    if settlement and settlement.amends_id:
        previous = PaymentDocument.objects.filter(payment=payment, settlement_id=settlement.amends_id, reverses__isnull=True).first()
        if previous:
            _issue(payment, kind="credit_note",
                   actor=actor, reverses=previous, money_at=previous.money_at,
                   method=previous.settlement_method, reference=previous.settlement_reference,
                   amount=previous.amount)
    return _issue(payment, kind="receipt", actor=actor, settlement=settlement,
                  money_at=settlement.received_at if settlement else payment.updated_at,
                  method=settlement.method if settlement else payment.provider,
                  reference=settlement.reference if settlement else "",
                  amount=payment.amount if received_amount is None else received_amount)


@transaction.atomic
def issue_credit_note(refund, *, actor=None):
    # Same lock order as refunds and settlements: Payment before the tenant counter.
    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    refund = Refund.objects.get(pk=refund.pk)
    if refund.status != Refund.Status.SUCCEEDED:
        raise ValueError("Only succeeded refunds receive a credit note.")
    if refund.amends_id:
        previous = PaymentDocument.objects.filter(payment=payment, refund_id=refund.amends_id, reverses__isnull=True).first()
        if previous:
            _issue(payment, kind="receipt", actor=actor,
                   reverses=previous, money_at=previous.money_at, method=previous.settlement_method,
                   reference=previous.settlement_reference, amount=previous.amount)
    return _issue(payment, kind="credit_note", actor=actor,
                  refund=refund, money_at=refund.refunded_at or refund.settled_at,
                  method=refund.method or refund.provider, reference=refund.reference, amount=refund.amount)


def _issue(payment, *, kind, actor, money_at, method, reference, amount,
           settlement=None, refund=None, reverses=None):
    query = PaymentDocument.objects.filter(payment=payment, kind=kind)
    if reverses:
        query = query.filter(reverses=reverses)
    elif settlement:
        query = query.filter(settlement=settlement)
    elif refund:
        query = query.filter(refund=refund)
    else:
        query = query.filter(settlement__isnull=True, refund__isnull=True, reverses__isnull=True)
    existing = query.first()
    if existing:
        return existing
    space = payment.makerspace
    if not feature_enabled(space, "billing.documents") and (kind == "bill" or not payment.documents.exists()):
        return None
    # The parent row exists even before billing policy is configured. Locking it also
    # serializes concurrent first-use get_or_create and prefix edits through the API.
    Makerspace.objects.select_for_update().get(pk=space.pk)
    policy, _ = MakerspaceBillingSettings.objects.get_or_create(makerspace=space)
    policy = MakerspaceBillingSettings.objects.select_for_update().get(pk=policy.pk)
    from .tax.document_tax import plan_for
    plan = plan_for(payment, kind=kind, amount=amount, refund=refund, reverses=reverses)
    counter = "next_bill_number" if kind == "bill" else "next_document_number"
    prefix = policy.bill_prefix if kind == "bill" else policy.number_prefix
    taken = lambda value: PaymentDocument.objects.filter(makerspace=space, number=value).exists()  # noqa: E731
    from .numbering_fy_receipts import allocate_receipt, applies as fy_receipt
    fy_plain = plan is None and fy_receipt(space, kind)
    if fy_plain:
        # Parity O-B3: tax off, `billing.fy_receipts` on -- the receipt joins its own per-FY series.
        fy = allocate_receipt(space, policy, taken=taken, actor=actor)
        numbering = {"sequence": fy.sequence, "number": fy.number, "number_series": fy.series,
                     "fy_start": fy.fy_start}
    elif plan is None:
        number = getattr(policy, counter)
        while PaymentDocument.objects.filter(makerspace=space, number=f"{prefix}{number:06d}").exists():
            number += 1
        numbering = {"sequence": number, "number": f"{prefix}{number:06d}"}
    else:
        from .numbering_fy import allocate
        fy = allocate(space, plan.policy, kind, taken=lambda value: PaymentDocument.objects.filter(
            makerspace=space, number=value).exists())
        numbering = {"sequence": fy.sequence, "number": fy.number, "number_series": fy.series,
                     "fy_start": fy.fy_start, "tax_breakdown": plan.breakdown}
    from .document_snapshot import issuer_snapshot
    from .document_pdf_assets import retain_logo
    logo_key, logo_digest = retain_logo(space)
    lines = [{"label": payment.subject_label or payment.get_subject_type_display(),
              "quantity": "1", "unit_amount": str(amount), "total": str(amount)}]
    sac = (plan.breakdown or {}).get("sac_code") if plan is not None and plan.breakdown else ""
    if sac and (plan.breakdown or {}).get("mode") == "gst_india":
        lines[0]["sac_code"] = sac  # parity O-B3: the SAC the charge froze (the plan's own when `billing.plan_sac`)
    if len(lines) > 200:
        raise ValueError("A payment document supports at most 200 lines.")
    document = PaymentDocument.objects.create(
        makerspace=space, payment=payment, settlement=settlement, refund=refund,
        reverses=reverses, **numbering,
        kind=kind, issued_by=actor,
        issuer=issuer_snapshot(payment, policy, kind),
        branding_logo_key=logo_key, branding_logo_sha256=logo_digest,
        payer_label=payment.member.username if payment.member_id else "Account-less payer",
        payer_type="member" if payment.member_id else "account_less",
        lines=lines,
        amount=amount, currency=payment.currency, settlement_method=method,
        settlement_reference=reference, money_at=money_at,
    )
    if plan is None and not fy_plain:
        setattr(policy, counter, number + 1)
        policy.save(update_fields=[counter])
    audit.record(actor, "payment.document_issued", makerspace=space, target=document,
                 meta={"kind": kind, "number": document.number})
    from apps.payments.notifications_p2 import notify_document
    notify_document(document)
    return document
