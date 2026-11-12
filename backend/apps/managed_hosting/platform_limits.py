"""Monthly limits on a space's use of the PLATFORM credentials (owner, 2026-11-11).

* Applies to EVERY space, own or hosted, and independent of ``plans_enabled()``: it is about the
  operator's cost when the space has no credentials of its own (decision 240 fallback).
* Counted ONLY on the platform-credential path. A space's own SMTP/Twilio/Razorpay/wallet
  credentials are never counted or limited here.
* Default is unlimited: nothing is enforced until the superadmin stores a value in the space's
  ``resource_limit_overrides`` (``None``/-1/absent = unlimited).
* Payments: the limit refuses only a NEW online page on the platform Connect rail; offline
  settlement and the space's own gateway are never touched.
"""
from datetime import UTC, datetime

from apps.makerspaces.limits_core import PLATFORM_CREDENTIAL_LIMIT_KEYS

LABELS = {
    "platform_email_monthly": "emails sent with the platform mail account this month",
    "platform_sms_monthly": "SMS sent with the platform SMS account this month",
    "platform_whatsapp_monthly": "WhatsApp messages sent with the platform account this month",
    "platform_push_monthly": "push deliveries (one per recipient or device) through the platform this month",
    "platform_wallet_monthly": "new wallet passes signed with the platform certificates this month",
    "platform_payments_monthly_count": "online payments through the platform rail this month",
    "platform_payments_monthly_amount": "money taken through the platform rail this month (per currency)",
}
CHANNEL_KEYS = {"email": "platform_email_monthly", "sms": "platform_sms_monthly",
                "whatsapp": "platform_whatsapp_monthly", "native_push": "platform_push_monthly"}
RAIL_ERROR_CODE = "platform_rail_limit_reached"


def platform_limit(makerspace, key):
    """The superadmin limit for ``key`` (int), or None = unlimited (the default)."""
    overrides = makerspace.resource_limit_overrides or {}
    if key not in overrides:
        from .enforcement import NOT_SET, plan_limit  # plan fallback for a hosted space (#261)
        planned = plan_limit(makerspace, key)
        if planned is NOT_SET:  # decision 328a: then the platform default for the key, then no limit
            from .limit_defaults import platform_default
            return platform_default(key)
        return planned
    value = overrides[key]
    if value is None or isinstance(value, bool) or value == -1:
        return None
    return int(value)


def _month_start():
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def uses_own_email(makerspace) -> bool:
    from apps.integrations.space_smtp_gate import own_smtp_in_use, smtp_verified
    # An own SMTP account that has not passed its test is not used (parity E-B8), so its mail is platform mail.
    if own_smtp_in_use(makerspace):
        return smtp_verified(makerspace)
    return bool((getattr(makerspace, "email_provider", "") or "").strip())


def platform_used(makerspace, key, currency=None):
    """Usage this month on the platform path only; the amount key sums one currency (all if None)."""
    start = _month_start()
    if key == "platform_email_monthly":
        from apps.integrations.models import EmailLog
        # Stamped at ENQUEUE, so queued mail counts; a skipped or failed row stops counting (released).
        return EmailLog.objects.filter(makerspace=makerspace, provider_source="platform", created_at__gte=start
                                       ).exclude(status__in=(EmailLog.Status.SKIPPED, EmailLog.Status.FAILED)).count()
    if key in ("platform_sms_monthly", "platform_whatsapp_monthly"):
        from apps.integrations.models_contract import NotificationDelivery
        channel = key.removeprefix("platform_").removesuffix("_monthly")
        return NotificationDelivery.objects.filter(makerspace=makerspace, channel=channel, provider_source="platform",
                                                   created_at__gte=start).exclude(state="skipped").exclude(
            state="failed", retryable=False).count()
    if key == "platform_push_monthly":
        # Unit: ONE PUSH DELIVERY to one recipient (message pipeline) or one device (staff alert attempt) on the
        # platform path, queued rows included, skipped and permanently failed ones released. Native push has no
        # own-credential path, so every push row IS platform; the staff-alert rows say so in `provider_source`.
        from apps.integrations.models_contract import NotificationDelivery
        from apps.integrations.models_tracking import PushDeliveryAttempt
        pipeline = NotificationDelivery.objects.filter(makerspace=makerspace, channel="native_push",
                                                       created_at__gte=start).exclude(state="skipped").exclude(
            state="failed", retryable=False).count()
        staff = PushDeliveryAttempt.objects.filter(delivery_log__makerspace=makerspace, provider_source="platform",
                                                   created_at__gte=start).exclude(status="skipped").count()
        return pipeline + staff
    if key == "platform_wallet_monthly":
        # Only passes SIGNED with the platform certificates: `wallet_pass.issued` stamps `source` at issue time
        # (a space's own certificates are never counted). Unit: NEW passes issued this month; a re-issue of a
        # pass from an earlier month is not a new pass. Queued, not-yet-signed passes count once they issue.
        from apps.audit.models import AuditLog
        from apps.card_designs.models_wallet import WalletPass
        ids = AuditLog.objects.filter(action="wallet_pass.issued", makerspace=makerspace, created_at__gte=start,
                                      meta__source="platform").values_list("meta__pass_id", flat=True)
        return WalletPass.objects.filter(pk__in={i for i in ids if i is not None}, created_at__gte=start).count()
    from django.db.models import Sum

    from apps.payments.models import Payment
    rows = Payment.objects.filter(makerspace=makerspace, stripe_provider=Payment.StripeProvider.CONNECT,
                                  created_at__gte=start).exclude(status=Payment.Status.CANCELED)
    if key == "platform_payments_monthly_count":
        return rows.count()
    if currency:
        rows = rows.filter(currency=currency.lower())
    return int(rows.aggregate(t=Sum("amount"))["t"] or 0)


def platform_refusal(makerspace, key, adding=1, *, currency=None):
    """A refusal message when the limit would be exceeded, else None (unlimited by default)."""
    if key not in PLATFORM_CREDENTIAL_LIMIT_KEYS or makerspace is None:
        return None
    try:
        limit = platform_limit(makerspace, key)
        if limit is None:
            return None
        if platform_used(makerspace, key, currency) + adding > limit:
            return f"This space has used the {LABELS[key]} allowed by the platform ({limit})."
    except Exception:  # never break delivery on a counting failure
        return None
    return None


def note_reached(makerspace, key):
    """Audit entry ONCE per (space, key, month); fail-safe. The staff notice reads it."""
    try:
        from apps.audit import services as audit
        from apps.audit.models import AuditLog
        period = _month_start().strftime("%Y-%m")
        if AuditLog.objects.filter(action="platform_credential_limit.reached", makerspace=makerspace,
                                   meta__key=key, meta__period=period).exists():
            return
        audit.record(None, "platform_credential_limit.reached", makerspace=makerspace, target=makerspace,
                     meta={"key": key, "period": period})
        from .limit_notices import notify_reached
        notify_reached(makerspace, key, period, LABELS[key])
    except Exception:
        return


def channel_refusal(makerspace, channel, *, queued=False):
    """Refusal for one outgoing message on the platform path of ``channel``; records the notice once.

    ``queued``: the delivery row already exists (and counts), so the Nth message is not over the limit.
    """
    key = CHANNEL_KEYS.get(channel)
    message = platform_refusal(makerspace, key, 0 if queued else 1) if key else None
    if message:
        note_reached(makerspace, key)
    return message


def _limit_set_after(makerspace, key, payment):
    """True when the superadmin changed ``key`` AFTER this charge was raised (retroactive limits spare it)."""
    from apps.audit.models import AuditLog
    return AuditLog.objects.filter(action="space_control.limits_changed", makerspace=makerspace,
                                   created_at__gt=payment.created_at, meta__changed__contains=[key]).exists()


def _charge_beyond_limit(makerspace, payment, key):
    """Quota rule (decision 281): a charge is refused only if the quota was ALREADY reached when it was raised.

    The rank is "charges raised this month before this one" (count) or their sum in this currency (amount).
    A charge raised before the limit was reached, or before the limit was set/lowered, stays payable.
    """
    limit = platform_limit(makerspace, key)
    if limit is None or _limit_set_after(makerspace, key, payment):
        return None
    from django.db.models import Q, Sum

    from apps.payments.models import Payment
    earlier = Payment.objects.filter(
        makerspace=makerspace, stripe_provider=Payment.StripeProvider.CONNECT, created_at__gte=_month_start()
    ).exclude(status=Payment.Status.CANCELED).filter(
        Q(created_at__lt=payment.created_at) | Q(created_at=payment.created_at, pk__lt=payment.pk))
    if key == "platform_payments_monthly_count":
        before = earlier.count()
    else:
        before = int(earlier.filter(currency=payment.currency.lower()).aggregate(t=Sum("amount"))["t"] or 0)
    if before >= limit:
        return f"This space has used the {LABELS[key]} allowed by the platform ({limit})."
    return None


def rail_refusal(makerspace, payment):
    """Refusal for starting an online page on the platform Connect rail, for a charge raised AFTER the quota."""
    try:
        for key in ("platform_payments_monthly_count", "platform_payments_monthly_amount"):
            message = _charge_beyond_limit(makerspace, payment, key)
            if message:
                return message
    except Exception:  # never break a payment on a counting failure
        return None
    return None


def usage_rows(makerspace):
    """Every platform-credential row (limit None = unlimited) for the console and the SM page."""
    rows = []
    for key in sorted(PLATFORM_CREDENTIAL_LIMIT_KEYS):
        limit = platform_limit(makerspace, key)
        try:
            used = platform_used(makerspace, key)
        except Exception:
            used = None
        rows.append({"key": key, "label": LABELS[key], "unit": "amount" if key.endswith("amount") else "count",
                     "limit": limit, "used": used,
                     "percent": round(used * 100 / limit, 1) if limit and used is not None else None})
    return rows
