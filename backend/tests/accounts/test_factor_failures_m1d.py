"""Second factors expire, cannot be replayed, and commit their attempt counters."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import account_deletion as deletion, reauthentication as auth
from apps.accounts import reauthentication_factors as factors, reauthentication_intents as intents
from apps.accounts import reauthentication_phone as phone
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.models_social import SocialIdentity
from tests.accounts.test_reauth_proof_m1d import configure_sms
from tests.accounts.test_reauthentication import request
from tests.accounts.test_support_m1d import account, m1d_config

pytestmark = pytest.mark.django_db


def email_factor(monkeypatch):
    user = account(password=None)
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="linked")
    req = request(user, surface="member")
    state, parent = intents._new(req, "social_reauth", provider="github", nonce="nonce")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **kw: {"sub": "linked"})
    send = Mock(return_value=SimpleNamespace(status="sent"))
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", send)
    factor = intents.complete_social(req, state=state, nonce="nonce")
    code = send.call_args.kwargs["text_body"].split(" is ")[1].split(".")[0]
    row = MFAChallenge.objects.get(token_digest=intents._digest(factor["factor_token"]))
    return user, req, factor["factor_token"], row, code


@pytest.mark.parametrize("failure", ["expired", "attempts"])
def test_email_second_factor_is_expiring_and_attempt_capped(failure, monkeypatch):
    user, req, token, row, code = email_factor(monkeypatch)
    if failure == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=["expires_at"])
    else:
        row.context["code_digest"] = "0" * 64
        row.save(update_fields=["context"])
        for attempt in range(5):
            with pytest.raises(AuthenticationFailed):
                factors.confirm_factor(req, token=token, code="123456")
            row.refresh_from_db()
            assert row.attempts == attempt + 1
        assert row.consumed_at
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=token, code=code)
    assert auth.current(req) is None
    with pytest.raises(auth.RecentAuthenticationRequired):
        deletion.request_deletion(req)
    user.refresh_from_db()
    assert user.deletion_requested_at is None


def verified_phone(user):
    user.phone_e164 = "+15551234567"
    user.save(update_fields=["phone_e164"])
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])


def test_github_can_use_phone_second_factor_bound_to_one_exact_otp(monkeypatch):
    configure_sms(monkeypatch)
    user = account(password=None)
    verified_phone(user)
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="linked")
    req = request(user, surface="member")
    state, _ = intents._new(req, "social_reauth", provider="github", nonce="nonce")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **kw: {"sub": "linked"})
    result = intents.complete_social(req, state=state, nonce="nonce")
    assert result["factor_required"] == "phone"
    challenge = PhoneVerificationChallenge.objects.get(user=user)
    factor = MFAChallenge.objects.get(token_digest=intents._digest(result["factor_token"]))
    assert factor.context["phone_challenge_id"] == challenge.pk
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=result["factor_token"], code="000000")
    challenge.refresh_from_db()
    assert challenge.failed_attempts == 1
    assert factors.confirm_factor(req, token=result["factor_token"], code="654321")["verified"]
    assert deletion.request_deletion(req)["deleted_at"]


def test_phone_failed_attempts_and_consumption_survive_deletion_transaction_rollback(monkeypatch):
    configure_sms(monkeypatch)
    user = account(password=None)
    verified_phone(user)
    req = request(user, surface="member")
    result = phone.start(req)
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="000000")
    assert phone.confirm(req, token=result["token"], code="654321")["verified"]
    real_audit = deletion.audit.record

    def fail_departure(actor, action, **kwargs):
        if action == "account.deletion_requested":
            raise RuntimeError("late transaction failure")
        return real_audit(actor, action, **kwargs)

    monkeypatch.setattr(deletion.audit, "record", fail_departure)
    with pytest.raises(RuntimeError):
        deletion.request_deletion(req)
    user.refresh_from_db()
    challenge = PhoneVerificationChallenge.objects.get(user=user)
    intent = MFAChallenge.objects.get(token_digest=intents._digest(result["token"]))
    assert user.is_active and user.deletion_requested_at is None
    assert challenge.failed_attempts == 1 and challenge.consumed_at
    assert intent.attempts == 1 and intent.consumed_at
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="654321")
