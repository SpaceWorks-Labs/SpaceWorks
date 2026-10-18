"""Local guards for changing the merchant behind outstanding collections."""

from cryptography.fernet import InvalidToken
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Q
from rest_framework.exceptions import APIException

from apps.payments.models import Payment


RAZORPAY_CREDENTIAL_FIELDS = (
    "razorpay_key_id", "razorpay_key_secret", "razorpay_webhook_secret",
)


class PaymentProviderConflict(APIException):
    status_code = 409
    default_code = "payment_provider_conflict"
    default_detail = {
        "code": "payment_provider_conflict",
        "detail": (
            "Cannot switch payment provider while online collections on the other "
            "provider are pending. Settle or close those collections first."
        ),
    }


def pending_online_collections(makerspace):
    # Same handle/expiry rule as tenant-migration preflight, including native Orders
    # and PaymentIntents. A debt with no provider handle is safe to keep in the ledger.
    return Payment.objects.filter(
        makerspace=makerspace,
        status=Payment.Status.PENDING,
        stripe_checkout_session_expired_at__isnull=True,
    ).filter(
        Q(external_order_id__isnull=False)
        | ~Q(checkout_url="")
        | Q(stripe_checkout_session_id__isnull=False)
        | ~Q(stripe_checkout_url="")
        | Q(stripe_payment_intent_id__isnull=False)
    )


def validate_provider_change(payment_settings, changes):
    provider = changes.get("provider", payment_settings.provider)
    if provider == payment_settings.provider:
        return
    other_provider = "razorpay" if provider == "stripe" else "stripe"
    if pending_online_collections(payment_settings.makerspace).filter(
        provider=other_provider,
    ).exists():
        raise PaymentProviderConflict()


def validate_razorpay_rotation(payment_settings, changes):
    changed = []
    for field in RAZORPAY_CREDENTIAL_FIELDS:
        if field not in changes:
            continue
        try:
            getter = getattr(payment_settings, f"get_{field}", None)
            current = getter() if getter else getattr(payment_settings, field)
        except (ImproperlyConfigured, InvalidToken):
            current = None
        if changes[field] != current:
            changed.append(field)
    if changed and pending_online_collections(payment_settings.makerspace).filter(
        provider=Payment.Provider.RAZORPAY,
    ).exists():
        raise ValidationError({field: (
            "Cannot change Razorpay credentials while online collections are pending."
        ) for field in changed})
