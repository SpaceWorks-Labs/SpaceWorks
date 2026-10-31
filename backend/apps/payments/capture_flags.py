"""Accept, flag and hold unexpected online captures; staff decide (lane L5, G24).

Recording runs inside the webhook transaction, under the Payment lock the settlement
path already holds. Resolution is a staff action and the only way a held receipt is
issued. No function here moves money: `refund_case` opens an entitlement that a staff
member must still approve through `services_refund_decisions`.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.payments.exceptions_refunds import RefundCaseConflict
from apps.payments.models import Payment, RefundCase
from apps.payments.models_capture_flags import PaymentCaptureFlag as Flag
from apps.payments.money import minor_unit_exponent, to_minor_units


class FlagConflict(RefundCaseConflict):
    pass


def receipt_held(payment):
    return Flag.objects.filter(payment=payment, kind__in=Flag.HOLDS_RECEIPT, resolution="").exists()


def captured_amount(minor, currency, payment):
    """Ledger amount of a capture in the charge currency, or None if it cannot be receipted."""
    if (currency or "").lower() != payment.currency:
        return None
    value = Decimal(int(minor)).scaleb(-minor_unit_exponent(currency))
    return value if value == value.quantize(Decimal("0.01")) and value > 0 else None


def differs(payment, minor, currency):
    """True when a provider told us what it captured and it is not the charge."""
    if not minor and not currency:
        return False
    if currency and currency.lower() != payment.currency:
        return True
    return bool(minor) and int(minor) != to_minor_units(payment.amount, payment.currency)


def record_flag(payment, *, kind, provider, provider_payment_id="", event_id="", minor=0, currency="",
                prior_status=""):
    flag, created = Flag.objects.get_or_create(
        payment=payment, kind=kind, provider_payment_id=provider_payment_id or "",
        defaults=dict(makerspace_id=payment.makerspace_id, provider=provider, provider_event_id=event_id or "",
                      captured_minor=int(minor or 0), captured_currency=(currency or "").lower(),
                      captured_amount=captured_amount(minor, currency or payment.currency, payment) if minor else payment.amount,
                      prior_status=prior_status))
    if not created:
        return flag
    audit.record(None, "payment.capture_flagged", makerspace=payment.makerspace, target=payment, meta={
        "flag_id": flag.pk, "kind": kind, "provider": provider, "prior_status": prior_status,
        "amount_minor": flag.captured_minor, "currency": flag.captured_currency})
    if kind in Flag.HOLDS_RECEIPT:
        audit.record(None, "payment.document_held", makerspace=payment.makerspace, target=payment,
                     meta={"flag_id": flag.pk, "kind": kind})
    from apps.payments.notifications_l5 import notify_capture_flag
    transaction.on_commit(lambda: notify_capture_flag(flag))
    return flag


def flag_after_terminal(payment, *, provider, provider_payment_id, event_id, minor, currency, prior_status):
    """A capture for a charge that was no longer pending. Caller holds the Payment lock."""
    if prior_status == Payment.Status.CANCELED:
        promote_cancelled(payment, provider=provider, provider_payment_id=provider_payment_id)
        return record_flag(payment, kind=Flag.Kind.LATE, provider=provider, provider_payment_id=provider_payment_id,
                           event_id=event_id, minor=minor, currency=currency, prior_status=prior_status)
    if prior_status == Payment.Status.PAID_OFFLINE or (
            provider_payment_id and provider_payment_id not in _capture_ids(payment)):
        return record_flag(payment, kind=Flag.Kind.DUPLICATE, provider=provider,
                           provider_payment_id=provider_payment_id, event_id=event_id, minor=minor,
                           currency=currency, prior_status=prior_status)
    return None


def _capture_ids(payment):
    return {value for value in (payment.external_payment_id, payment.stripe_payment_intent_id) if value}


def promote_cancelled(payment, *, provider, provider_payment_id):
    """Record money that arrived for a cancelled charge: cancelled -> paid_online.

    The trigger allows exactly this transition, amount unchanged, only under the
    transaction-local GUC. No receipt (the flag holds it), no admission resume, no
    member notice: a cancelled subject stays cancelled and staff decide.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_late_capture_settlement = 'on'")
    updates = {"status": Payment.Status.PAID_ONLINE, "updated_at": timezone.now()}
    if provider == Payment.Provider.RAZORPAY and provider_payment_id and not payment.external_payment_id:
        updates["external_payment_id"] = provider_payment_id
    if provider == Payment.Provider.STRIPE and provider_payment_id and not payment.stripe_payment_intent_id:
        updates["stripe_payment_intent_id"] = provider_payment_id
    if Payment.objects.filter(pk=payment.pk, status=Payment.Status.CANCELED).update(**updates) != 1:
        raise RuntimeError("The cancelled payment could not record its late capture.")
    for key, value in updates.items():
        setattr(payment, key, value)
    audit.record(None, "payment.paid_online", makerspace=payment.makerspace, target=payment,
                 meta={"provider": provider, "late_capture": True})


@transaction.atomic
def resolve_flag(*, actor, makerspace_id, flag_id, resolution, note="", amount=None):
    from apps.payments.reconciliation import _require_record_authority, _require_subject_authority

    flag = Flag.objects.filter(pk=flag_id, makerspace_id=makerspace_id).first()
    if flag is None:
        raise NotFound("Capture flag not found.")
    payment = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=flag.payment_id)
    flag = Flag.objects.select_for_update().get(pk=flag.pk)
    if not flag.is_open:
        raise FlagConflict("This flag has already been resolved.", "capture_flag_resolved")
    if resolution == Flag.Resolution.REFUND_CASE:
        _require_subject_authority(actor, [payment])
        flag.refund_case = _open_flag_case(payment, flag, actor, amount)
    else:
        _require_record_authority(actor, [payment])
    if resolution == Flag.Resolution.ISSUE_RECEIVED:
        if flag.kind not in Flag.HOLDS_RECEIPT or flag.captured_amount is None:
            raise FlagConflict("This capture cannot be receipted; open a refund case instead.", "document_held")
    elif resolution == Flag.Resolution.ACKNOWLEDGED and not (note or "").strip():
        raise FlagConflict("Say what happened, for example where the money was refunded.", "note_required")
    flag.resolution, flag.resolution_note = resolution, (note or "").strip()[:500]
    flag.resolved_by, flag.resolved_at = actor, timezone.now()
    flag.save()
    audit.record(actor, "payment.capture_flag_resolved", makerspace=payment.makerspace, target=payment,
                 meta={"flag_id": flag.pk, "kind": flag.kind, "resolution": resolution})
    if flag.kind in Flag.HOLDS_RECEIPT and not receipt_held(payment):
        from apps.payments.documents import issue_receipt
        received = flag.captured_amount if resolution == Flag.Resolution.ISSUE_RECEIVED else None
        document = issue_receipt(payment, actor=actor, received_amount=received) if received else None
        audit.record(actor, "payment.document_released", makerspace=payment.makerspace, target=payment,
                     meta={"flag_id": flag.pk, "document_id": document.pk if document else None})
    return flag


def _open_flag_case(payment, flag, actor, amount):
    """A case for the flagged money, for a staff member to approve or decline.

    Kind `request` (staff-opened, no requesting member), never `due`: the one policy
    assessment a payment may receive stays free for a later cancellation.
    """
    from apps.payments.refund_policy import area_for, refundable_balance
    from apps.payments.services_refund_cases import record_case

    if RefundCase.objects.filter(payment=payment, status__in=RefundCase.ACTIVE_STATUSES).exists():
        raise FlagConflict("A refund case is already open for this charge.", "refund_request_exists")
    default = flag.captured_amount or payment.amount
    if flag.kind == Flag.Kind.MISMATCH and flag.captured_amount and flag.captured_amount > payment.amount:
        default = flag.captured_amount - payment.amount
    due = min(Decimal(amount) if amount is not None else default, refundable_balance(payment))
    if due <= 0:
        raise FlagConflict("Nothing is left to refund on this charge.", "refund_exceeds_balance")
    case = RefundCase.objects.create(
        payment=payment, kind=RefundCase.Kind.REQUEST, area=area_for(payment),
        reason_code=RefundCase.ReasonCode.CAPTURE_FLAGGED, due_amount=due,
        policy_snapshot={"source": "capture_flag", "flag_id": flag.pk, "kind": flag.kind})
    record_case(actor, "payment.refund_case_opened", case, due_amount=str(due), reason_code=case.reason_code)
    return case
