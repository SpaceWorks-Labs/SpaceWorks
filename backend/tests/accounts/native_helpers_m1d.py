"""Phase-1d device proofs use the integrated registration-owned signing identity."""

from apps.accounts.models_social import PlatformSocialAuthSettings
from tests.accounts.mobile_integration_helpers import PREFIX, registration
from tests.accounts.test_social_first_grant import APP_ID, OAUTH_AUDIENCE, issue_challenge


def configure_apple(settings):
    settings.DEVICE_ATTESTATION_APPS = {}
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = "https://attest.example.test/verify"
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = "provider-secret"
    return registration("apple", app_id=APP_ID, environment="development")


def configure_native_social(settings):
    row = configure_apple(settings)
    social = PlatformSocialAuthSettings.load()
    social.google_ios_client_id = OAUTH_AUDIENCE
    social.google_android_client_id = OAUTH_AUDIENCE
    social.save(update_fields=["google_ios_client_id", "google_android_client_id", "updated_at"])
    return row


def mock_attestation(monkeypatch, raw):
    class Response:
        status_code = 200

        def json(self):
            return {
                "verified": True, "subject": "attested-device-subject", "platform": "apple",
                "app_id": APP_ID, "signing_identity": PREFIX, "environment": "development",
                "challenge": raw,
            }

    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post", lambda *a, **kw: Response())


def attested_login(client, user, settings, monkeypatch, *, password="strong-device-password", staff_space=None):
    configure_apple(settings)
    raw = issue_challenge(client)
    mock_attestation(monkeypatch, raw)
    payload = {
        "username": user.username, "password": password, "platform": "apple",
        "app_id": APP_ID, "environment": "development", "challenge": raw,
        "attestation": {"assertion": "opaque-provider-payload"},
    }
    if staff_space is not None:
        # Release 2: a staff grant is a step-up on the person, fixed to one makerspace.
        payload.update(authority="staff", makerspace=staff_space.slug)
    return client.post("/api/v1/auth/device/login", payload, format="json"), payload


def attested_staff_login(client, user, settings, monkeypatch, *, password="strong-device-password"):
    from tests.accounts.mfa_helpers import complete_enrollment
    from apps.accounts.staff_identity import staff_makerspace_ids
    from apps.makerspaces.models import Makerspace
    space_id = min(staff_makerspace_ids(user))
    response, payload = attested_login(client, user, settings, monkeypatch, password=password,
                                       staff_space=Makerspace.objects.get(pk=space_id))
    assert response.status_code == 200 and response.data["mfa_required"]
    assert response.data["enrollment_required"]
    return complete_enrollment(client, response), payload
