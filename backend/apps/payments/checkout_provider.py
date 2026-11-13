"""Hosted provider requests and immutable currency/idempotency calculations."""

from decimal import Decimal, ROUND_HALF_UP

from apps.payments.money import (
    AmountNotCapturable, minor_unit_exponent, to_minor_units, to_provider_minor_units,
)


def _create_checkout_via_provider(payment, source, label, member_url):
    """Raise a hosted page through the provider seam and record the generic ids.

    Called with the Payment row already locked by `_create_checkout_url_atomic`, so the
    lock ordering (platform settings -> makerspace settings -> Payment) is unchanged.
    """
    from apps.payments.providers import CheckoutRequest, PaymentsUnavailable, get_provider

    try:
        amount_minor = to_provider_minor_units(payment.amount, payment.currency)
    except AmountNotCapturable as exc:
        raise PaymentsUnavailable("The charge amount is finer than the provider can capture.") from exc

    provider = get_provider(payment.provider)
    result = provider.create_checkout(
        source,
        CheckoutRequest(
            # Integer minor units. A float here is a rounding bug that reconciles as a
            # real money difference.
            amount_minor=amount_minor,
            currency=payment.currency,
            description=label,
            reference=str(payment.pk),
            success_url=f"{member_url}?checkout=success",
            cancel_url=f"{member_url}?checkout=cancelled",
            metadata={"payment_id": payment.pk, "makerspace_id": payment.makerspace_id},
            idempotency_key=_checkout_idempotency_key(payment),
        ),
    )
    payment.external_order_id = result.order_id
    payment.checkout_url = result.checkout_url
    # A fresh page is live again, exactly as the Stripe branch resets it.
    payment.stripe_checkout_session_expired_at = None
    payment.save(
        update_fields=[
            "external_order_id", "checkout_url", "stripe_checkout_session_expired_at",
            "online_rail", "updated_at",
        ]
    )
    return result.checkout_url


def _value(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _application_fee_amount(amount, basis_points, currency):
    """The Connect platform fee in provider minor units, stamped once on a NEW charge.

    Three-decimal currencies (KWD, BHD, OMR, JOD, TND) move in 10-fils steps at Stripe, so their
    fee is rounded half-up to a multiple of 10 (PAY-REVIEW 0.12.0); a stray fils made Stripe
    refuse the checkout. Existing charges keep the fee already stored on their row.
    """
    minor_units = Decimal(to_minor_units(amount, currency))
    step = Decimal(10) if minor_unit_exponent(currency) == 3 else Decimal(1)
    steps = (minor_units * Decimal(basis_points) / Decimal(10000) / step).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(steps * step)


def _checkout_idempotency_key(payment):
    generation = 0
    if payment.stripe_checkout_session_expired_at is not None:
        generation = int(
            payment.stripe_checkout_session_expired_at.timestamp() * 1_000_000
        )
    return f"payment-checkout-{payment.pk}-{generation}"
