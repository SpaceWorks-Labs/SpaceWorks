"""S-B: only sign-in purposes complete a sign-in; a re-authentication intent never does."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mfa_challenges import start
from apps.accounts.mfa_crypto import totp
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.mfa_sessions import context
from tests.accounts.login_risk_helpers import ORIGIN, person
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db


class _Request:
    headers = {"Origin": ORIGIN}
    META = {"HTTP_ORIGIN": ORIGIN}


@pytest.mark.parametrize("purpose", ["reauth:mfa_change", "reauth:security_settings", "something_else"])
def test_reauth_intent_challenge_never_completes_a_sign_in(purpose):
    user = person(f"purpose-{purpose.replace(':', '-')}")
    _row, secret = enrolled(user)
    raw = start(user, context=context(None, surface="member"))["challenge"]
    challenge = MFAChallenge.objects.get(user=user)
    challenge.context = {**challenge.context, "purpose": purpose}
    challenge.save(update_fields=["context"])
    code = totp(secret, int(timezone.now().timestamp() // 30))
    response = APIClient().post("/api/v1/auth/mfa/verify", {"challenge": raw, "code": code}, format="json")
    assert response.status_code == 401
    assert MFAChallenge.objects.get(pk=challenge.pk).consumed_at is None


def test_login_purpose_and_factors_are_reported():
    user = person("purpose-login")
    enrolled(user, recovery_digests=["x"])
    result = start(user, context=context(None, surface="member"))
    assert result["purpose"] == "login" and result["factors"] == ["totp", "recovery"]
    assert result["enrollment_required"] is False


def test_a_risk_code_never_enrols():
    user = person("purpose-risk-enrol")
    from apps.accounts.login_security_contract import PURPOSE_RISK
    raw = start(user, context=context(None, surface="member"), purpose=PURPOSE_RISK)["challenge"]
    response = APIClient().post("/api/v1/auth/mfa/enroll", {"challenge": raw}, format="json")
    assert response.status_code in (401, 403)
