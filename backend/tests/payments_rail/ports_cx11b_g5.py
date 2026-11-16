"""Replace external Stripe I/O only; source resolution and all ledger services stay real."""
from types import SimpleNamespace

from apps.payments import stripe_client


def configure(s, monkeypatch):
    s.rail.provider = "stripe"
    s.rail.stripe_publishable_key = "pk_test_g5"
    s.rail.set_stripe_secret_key("sk_test_g5")
    s.rail.set_stripe_webhook_secret("whsec_g5")
    s.rail.save()
    calls = []
    def checkout(source, *, idempotency_key, **data):
        calls.append(("checkout", idempotency_key, data))
        return {"id": "cs_g5", "url": "https://checkout.example.test/g5"}
    def intent(source, *, idempotency_key, **data):
        calls.append(("intent", idempotency_key, data))
        return {"id": "pi_g5", "client_secret": "pi_g5_secret"}
    def refund(source, *, idempotency_key, **data):
        calls.append(("refund", idempotency_key, data))
        return {"id": "re_g5", "status": "succeeded"}
    monkeypatch.setattr(stripe_client, "create_checkout_session", checkout)
    monkeypatch.setattr(stripe_client, "create_payment_intent", intent)
    monkeypatch.setattr(stripe_client, "create_refund", refund)
    return SimpleNamespace(calls=calls)
