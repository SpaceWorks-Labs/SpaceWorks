"""Phone OTP device delivery keeps enumeration, attempt caps and member authority."""

from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.attestation import AttestationRejected, AttestationUnavailable
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceGrant
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.services_phone import MAX_FAILED_ATTEMPTS
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.native_helpers_m1d import configure_apple, mock_attestation
from tests.accounts.test_phone_auth_p8 import (
    LOGIN_CONFIRM, LOGIN_START, NUMBER, OTHER_NUMBER, code_from, sms_on,
    verified_member,
)
from tests.accounts.test_social_first_grant import issue_challenge
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def start_device(client, challenge, *, phone=NUMBER, client_platform="ios"):
    return client.post(LOGIN_START, {
        "phone": phone, "delivery": "device", "client_platform": client_platform,
        "challenge": challenge,
    }, format="json")


def confirm_device(client, challenge, code, *, client_platform="ios"):
    return client.post(LOGIN_CONFIRM, {
        "phone": NUMBER, "code": code, "delivery": "device",
        "client_platform": client_platform, "challenge": challenge,
        "attestation": {"assertion": "opaque"},
    }, format="json")


def test_device_start_ack_is_uniform_for_invalid_challenges_and_unknown_numbers(
    settings, sms_on,
):
    configure_apple(settings)
    user = verified_member()
    challenge = issue_challenge(APIClient())
    # Invalid first, so cooldown cannot conceal an incorrectly accepted challenge.
    invalid = start_device(APIClient(), "not-an-issued-challenge")
    assert invalid.status_code == 200
    assert sms_on == []
    unknown = start_device(APIClient(), challenge, phone=OTHER_NUMBER)
    assert unknown.status_code == 200 and sms_on == []
    valid = start_device(APIClient(), challenge)
    assert valid.status_code == 200
    assert valid.json() == invalid.json() == unknown.json()
    assert [message["to"] for message in sms_on] == [NUMBER]
    assert PhoneVerificationChallenge.objects.get(user=user).attestation_challenge_id


@pytest.mark.parametrize("staff,mfa", [(False, False), (True, False), (True, True)])
def test_phone_device_grant_is_always_member_without_cookies(
    settings, monkeypatch, sms_on, staff, mfa,
):
    configure_apple(settings)
    user = verified_member()
    space = make_space("phone-native-member-authority")
    assign_builtin_roles(user, space, "member")
    if staff:
        from tests.organizations.test_org_authority import grant, link, make_organization
        organization = make_organization("phone-native-delegate")
        link(organization, space, "manager")
        grant(organization, user, ["view_inventory"])
    if mfa:
        _, secret = enrolled(user)
    challenge = issue_challenge(APIClient())
    assert start_device(APIClient(), challenge).status_code == 200
    mock_attestation(monkeypatch, challenge)

    result = confirm_device(APIClient(), challenge, code_from(sms_on))

    assert result.status_code == 200
    assert not result.cookies and "Set-Cookie" not in result
    if mfa:
        assert result.data["mfa_required"] and "access" not in result.data
        assert not DeviceGrant.objects.filter(user=user).exists()
        result = APIClient().post("/api/v1/auth/mfa/verify", {
            "challenge": result.data["challenge"],
            "code": totp(secret, int(timezone.now().timestamp() // 30)),
        }, format="json")
        assert result.status_code == 200
    assert {"access", "refresh", "device_grant", "user"} <= set(result.data)
    assert DeviceGrant.objects.get(user=user).authority == "member"
    assert AccessToken(result.data["access"])["surface"] == "member"
    assert result.data["user"]["session_authority"] == "member"
    assert not result.cookies and "Set-Cookie" not in result
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {result.data['access']}")
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.data["session_authority"] == "member"
    assert client.get(
        f"/api/v1/admin/makerspace/{space.pk}/inventory",
        HTTP_X_MAKERSPACE_ID=str(space.pk),
    ).status_code == 403


def test_wrong_codes_commit_attempts_before_attestation_and_exhaust_the_cap(
    settings, monkeypatch, sms_on,
):
    configure_apple(settings)
    user = verified_member()
    challenge = issue_challenge(APIClient())
    assert start_device(APIClient(), challenge).status_code == 200
    real_code = code_from(sms_on)
    wrong_code = "000000" if real_code != "000000" else "111111"
    verifier = Mock(side_effect=AttestationRejected("bad attestation"))
    monkeypatch.setattr("apps.accounts.services_phone_device.verify_attestation", verifier)
    otp = PhoneVerificationChallenge.objects.get(user=user)
    for attempt in range(1, MAX_FAILED_ATTEMPTS + 1):
        assert confirm_device(APIClient(), challenge, wrong_code).status_code == 400
        otp.refresh_from_db()
        assert otp.failed_attempts == attempt
    assert confirm_device(APIClient(), challenge, real_code).status_code == 400
    verifier.assert_not_called()
    assert not DeviceGrant.objects.filter(user=user).exists()


def test_phone_attestation_outage_is_503_and_does_not_restore_the_otp(
    settings, monkeypatch, sms_on,
):
    configure_apple(settings)
    user = verified_member()
    challenge = issue_challenge(APIClient())
    assert start_device(APIClient(), challenge).status_code == 200
    monkeypatch.setattr("apps.accounts.services_phone_device.verify_attestation",
                        Mock(side_effect=AttestationUnavailable("offline")))
    result = confirm_device(APIClient(), challenge, code_from(sms_on))
    assert result.status_code == 503
    assert result.data["code"] == "attestation_unavailable"
    assert PhoneVerificationChallenge.objects.get(user=user).consumed_at is not None
    assert not DeviceGrant.objects.filter(user=user).exists()


@pytest.mark.parametrize("tamper", ["consumed", "foreign", "client_platform"])
def test_confirm_requires_the_original_live_challenge_and_platform(
    settings, monkeypatch, sms_on, tamper,
):
    configure_apple(settings)
    user = verified_member()
    challenge = issue_challenge(APIClient())
    assert start_device(APIClient(), challenge).status_code == 200
    otp = PhoneVerificationChallenge.objects.get(user=user)
    supplied, platform = challenge, "ios"
    if tamper == "consumed":
        row = otp.attestation_challenge
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
    elif tamper == "foreign":
        supplied = issue_challenge(APIClient())
    else:
        platform = "android"
    verifier = Mock()
    monkeypatch.setattr("apps.accounts.services_phone_device.verify_attestation", verifier)
    result = confirm_device(APIClient(), supplied, code_from(sms_on), client_platform=platform)
    assert result.status_code == 409
    assert result.data["code"] == "phone_device_restart_required"
    verifier.assert_not_called()
    otp.refresh_from_db()
    assert otp.consumed_at is not None
    assert not DeviceGrant.objects.filter(user=user).exists()


def test_start_platform_mismatch_is_uniform_but_sends_nothing(settings, sms_on):
    configure_apple(settings)
    verified_member()
    challenge = issue_challenge(APIClient())
    wrong = start_device(APIClient(), challenge, client_platform="android")
    assert wrong.status_code == 200 and sms_on == []
    valid = start_device(APIClient(), challenge)
    assert valid.status_code == 200 and valid.json() == wrong.json()
    assert len(sms_on) == 1


@pytest.mark.parametrize("change", ["delete", "inactive", "restricted", "generation"])
def test_account_changes_during_attestation_cannot_create_a_grant(
    settings, monkeypatch, sms_on, change,
):
    from apps.accounts.attestation import VerifiedAttestation
    from apps.accounts.models import User
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    configure_apple(settings)
    user = verified_member()
    challenge = issue_challenge(APIClient())
    assert start_device(APIClient(), challenge).status_code == 200
    before = OutstandingToken.objects.filter(user=user).count()

    def verify(*args):
        # OTP consumption has committed; this models departure/promotion while
        # the external attestation provider is responding.
        assert PhoneVerificationChallenge.objects.get(user=user).consumed_at
        changes = {
            "delete": {"is_active": False, "deletion_requested_at": timezone.now()},
            "inactive": {"is_active": False},
            "restricted": {"access_status": "restricted"},
            "generation": {"credential_generation": user.credential_generation + 1},
        }
        User.objects.filter(pk=user.pk).update(**changes[change])
        return VerifiedAttestation("subject", {})

    monkeypatch.setattr("apps.accounts.services_phone_device.verify_attestation", verify)
    result = confirm_device(APIClient(), challenge, code_from(sms_on))
    assert result.status_code == 409
    assert not DeviceGrant.objects.filter(user=user).exists()
    assert OutstandingToken.objects.filter(user=user).count() == before
    assert PhoneVerificationChallenge.objects.get(user=user).consumed_at
