"""Verifier readiness, explicit development bypass and API outage mapping."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.core.checks import Tags, run_checks
from rest_framework.test import APIClient

from apps.accounts.attestation import (
    AttestationRejected, AttestationUnavailable, VerifiedAttestation, configured_app,
    readiness_mode, verify_attestation,
)
from apps.accounts.models import DeviceGrant
from apps.accounts.models_attestation import PlatformAttestationSettings
from tests.accounts.mobile_integration_helpers import APP, FIRST, PREFIX, registration
from tests.accounts.native_helpers_m1d import attested_login, configure_native_social
from tests.accounts.test_social_first_grant import (
    complete_login, issue_challenge, mock_identity, request_nonce,
)
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def verifier_settings(settings):
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = ""
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = ""
    settings.DEVICE_ATTESTATION_DEV_INSECURE = False
    settings.DEBUG = False
    PlatformAttestationSettings.objects.all().delete()


def identity(platform="apple", *, environment="development", signing_identity=None):
    return SimpleNamespace(platform=platform, app_id=APP, environment=environment,
                           signing_identity=signing_identity or (PREFIX if platform == "apple" else FIRST))


def configure_entry(settings, challenge):
    settings.DEVICE_ATTESTATION_APPS = {}
    return registration(challenge.platform, environment=challenge.environment,
                        signing_identities=[challenge.signing_identity])


def enable_google(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    row = PlatformAttestationSettings.load()
    row.set_play_integrity_service_account('{"type":"service_account"}')
    row.save()


@pytest.mark.parametrize("platform", ["apple", "android"])
def test_external_mode_takes_precedence_over_in_process_credentials(
    settings, monkeypatch, platform,
):
    challenge = identity(platform)
    configure_entry(settings, challenge)
    if platform == "android":
        enable_google(settings)
    prefix = f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY"
    setattr(settings, f"{prefix}_URL", "https://attest.example.test/verify")
    setattr(settings, f"{prefix}_TOKEN", "secret")
    assert readiness_mode(platform, challenge.signing_identity) == "external"
    assert configured_app(platform, APP, "development") == challenge.signing_identity
    external = Mock(return_value="external-subject")
    target = "verify_apple_attestation" if platform == "apple" else "verify_android_attestation"
    monkeypatch.setattr(f"apps.accounts.attestation_{platform}.{target}", external)
    in_process = Mock(side_effect=AssertionError("wrong verifier selected"))
    module = "attestation_app_attest.verify_app_attest" if platform == "apple" else (
        "attestation_play_integrity.verify_play_integrity"
    )
    monkeypatch.setattr(f"apps.accounts.{module}", in_process)
    payload = {"assertion": "opaque"}
    assert verify_attestation(challenge, "raw", payload) == VerifiedAttestation(
        "external-subject", {"signing_identity": challenge.signing_identity},
    )
    external.assert_called_once_with(challenge, "raw", payload)
    in_process.assert_not_called()


@pytest.mark.parametrize("platform", ["apple", "android"])
def test_in_process_readiness_and_dispatch_preserve_metadata(settings, monkeypatch, platform):
    challenge = identity(platform)
    configure_entry(settings, challenge)
    if platform == "android":
        enable_google(settings)
    assert readiness_mode(platform, challenge.signing_identity) == "in_process"
    assert configured_app(platform, APP, "development") == challenge.signing_identity
    expected = VerifiedAttestation("verified-key", {
        "key_id": "key", "public_key": "pem", "signing_identity": challenge.signing_identity,
    })
    verifier = Mock(return_value=expected)
    module = "attestation_app_attest.verify_app_attest" if platform == "apple" else (
        "attestation_play_integrity.verify_play_integrity"
    )
    monkeypatch.setattr(f"apps.accounts.{module}", verifier)
    payload = {"type": "app_attest" if platform == "apple" else "play_integrity"}
    assert verify_attestation(challenge, "raw", payload) is expected
    verifier.assert_called_once_with(challenge, "raw", payload)


def test_unavailable_and_partial_external_configuration_do_not_enable_attestation(settings):
    challenge = identity("android", signing_identity="ab" * 32)
    configure_entry(settings, challenge)
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://attest.example.test/verify"
    assert readiness_mode("android", challenge.signing_identity) == "unavailable"
    with pytest.raises(AttestationUnavailable):
        configured_app("android", APP, "development")


@pytest.mark.parametrize("apple_in_process", [False, True])
@pytest.mark.parametrize("flag,debug,environment,accepted", [
    (True, True, "development", True),
    (False, True, "development", False),
    (True, False, "development", False),
    (True, True, "production", False),
])
def test_development_payload_requires_all_three_guards(
    settings, apple_in_process, flag, debug, environment, accepted,
):
    settings.DEVICE_ATTESTATION_DEV_INSECURE = flag
    settings.DEBUG = debug
    challenge = identity(
        "apple" if apple_in_process else "android", environment=environment,
        signing_identity="TEAMID1234" if apple_in_process else "ab" * 32,
    )
    configure_entry(settings, challenge)
    if accepted:
        mode = "in_process" if apple_in_process else "development_insecure"
        assert readiness_mode(challenge.platform, challenge.signing_identity) == mode
        assert configured_app(challenge.platform, APP, environment) == challenge.signing_identity
        assert verify_attestation(challenge, "raw", {"type": "development"}) == (
            VerifiedAttestation("development", {"signing_identity": challenge.signing_identity})
        )
    else:
        with pytest.raises((AttestationRejected, AttestationUnavailable)):
            verify_attestation(challenge, "raw", {"type": "development"})


def test_development_mode_requires_the_exact_explicit_payload(settings):
    settings.DEVICE_ATTESTATION_DEV_INSECURE = True
    settings.DEBUG = True
    challenge = identity("android")
    configure_entry(settings, challenge)
    for payload in ({"type": "development", "extra": True}, {"assertion": "opaque"}):
        with pytest.raises(AttestationRejected):
            verify_attestation(challenge, "raw", payload)


@pytest.mark.parametrize("debug,flag,expected", [
    (False, True, True), (True, True, False), (False, False, False),
])
def test_security_check_refuses_insecure_development_flag_in_production(settings, debug, flag, expected):
    settings.DEBUG = debug
    settings.DEVICE_ATTESTATION_DEV_INSECURE = flag
    ids = {error.id for error in run_checks(tags=[Tags.security])}
    # accounts.E001 is the staff-route registry check; attestation took E002 at the merge.
    assert ("accounts.E002" in ids) is expected


def test_password_attestation_outage_returns_503(settings, monkeypatch):
    user = make_user("password-attestation-outage", password="strong-device-password")
    verifier = Mock(side_effect=AttestationUnavailable("provider offline"))
    monkeypatch.setattr("apps.accounts.views_device.verify_attestation", verifier)
    result, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert result.status_code == 503
    assert result.data["code"] == "attestation_unavailable"
    assert not DeviceGrant.objects.filter(user=user).exists()


def test_social_attestation_outage_returns_503_instead_of_restart(settings, monkeypatch):
    configure_native_social(settings)
    user = make_user("social-attestation-outage")
    mock_identity(monkeypatch, user)
    challenge = issue_challenge(APIClient())
    nonce = request_nonce(APIClient(), challenge)
    assert nonce.status_code == 200
    monkeypatch.setattr("apps.accounts.social_nonces.verify_attestation",
                        Mock(side_effect=AttestationUnavailable("provider offline")))
    result = complete_login(APIClient(), nonce.data["nonce"], challenge)
    assert result.status_code == 503
    assert result.data["code"] == "attestation_unavailable"
    assert not DeviceGrant.objects.filter(user=user).exists()
