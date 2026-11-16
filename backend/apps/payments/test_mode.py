"""Parity C20: is this space charging through TEST credentials? Derived, never stored, never a secret.

Both providers put the mode in the PUBLIC half of the key pair: a Stripe publishable key starts `pk_test_` or
`pk_live_`, a Razorpay key id `rzp_test_` or `rzp_live_`. Only that public string is read, so the secret key is
never decrypted and the flag can be shown to every staff member who may open the payment settings.

Test money is real in the ledger but moved nothing: reports that list payments mark the ones a test key raised
(`payment_is_test`) so they are never added to live totals by eye. A Stripe Checkout session id carries its mode
(`cs_test_`); Razorpay order ids do not, so a Razorpay payment is never labelled test, and the space-level flag is
the authority for that provider.
"""

_TEST_PREFIXES = ("pk_test_", "rzp_test_")
_LIVE_PREFIXES = ("pk_live_", "rzp_live_")


def source_test_mode(source):
    """`True` (test), `False` (live) or `None` (no credentials, or a key of an unknown shape)."""
    key = getattr(source, "publishable_key", "") or ""
    if key.startswith(_TEST_PREFIXES):
        return True
    if key.startswith(_LIVE_PREFIXES):
        return False
    return None


def space_test_mode(makerspace):
    from apps.payments.resolution import resolve_payment_source
    source = resolve_payment_source(makerspace)
    return source_test_mode(source) if source is not None else None


def payment_is_test(payment):
    return bool(payment.provider == "stripe" and (payment.stripe_checkout_session_id or "").startswith("cs_test_"))
