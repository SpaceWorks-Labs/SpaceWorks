from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.attestation import AttestationRejected, AttestationUnavailable, VerifiedAttestation
from apps.accounts.device_activity import record_device_activity
from apps.accounts.models_activity import AttestationVerificationLog, DeviceActivityDay
from apps.integrations.models_tracking import SmsSendLog
from tests.accounts.account_factories import make_membership
from tests.return_helpers import make_space
from tests.test_native_push import device_client, push_member

pytestmark = pytest.mark.django_db


def test_activity_is_per_grant_tenant_local_day_and_null_is_unique(monkeypatch):
    space, other = make_space("activity-a"), make_space("activity-b")
    space.timezone, other.timezone = "Asia/Kolkata", "America/Los_Angeles"
    user = push_member("activity-user", space)
    first = user.makerspace_memberships.get(makerspace=space)
    second = make_membership(user, other)
    # Preserve these intentionally different local clocks without extra DB reads.
    first.makerspace, second.makerspace = space, other
    _, grant = device_client(user, space)
    now = timezone.datetime(2026, 10, 17, 1, tzinfo=timezone.get_fixed_timezone(0))
    monkeypatch.setattr("apps.accounts.device_activity.timezone.now", lambda: now)
    for _ in range(2):
        for membership in (first, second, None):
            record_device_activity(grant, membership)
    assert DeviceActivityDay.objects.count() == 3
    assert DeviceActivityDay.objects.get(makerspace=space).local_day.isoformat() == "2026-10-17"
    assert DeviceActivityDay.objects.get(makerspace=other).local_day.isoformat() == "2026-10-16"
    row = DeviceActivityDay.objects.get(makerspace=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        DeviceActivityDay.objects.create(grant=grant, makerspace=None, platform="apple", local_day=row.local_day)


def test_short_cache_is_set_only_after_commit(django_capture_on_commit_callbacks, django_assert_num_queries):
    space = make_space("activity-cache")
    _, grant = device_client(push_member("activity-cache-user", space), space)
    with django_capture_on_commit_callbacks(execute=True):
        record_device_activity(grant)
    with django_assert_num_queries(0):
        record_device_activity(grant)


def test_authentication_records_only_validated_selection(settings):
    settings.PUSH_TOKEN_HMAC_KEY = "a" * 64
    space = make_space("activity-auth")
    user = push_member("activity-auth-user", space)
    client, grant = device_client(user, space, platform="android")
    response = client.post("/api/v1/integrations/push/devices", {
        "token": "t" * 64, "provider": "fcm", "environment": "development",
    }, format="json")
    assert response.status_code == 201
    assert DeviceActivityDay.objects.filter(grant=grant, makerspace=space, platform="android").count() == 1
    authorization = client._credentials["HTTP_AUTHORIZATION"]
    # Member paths allow no selection; that activity belongs only to the NULL bucket.
    client.credentials(HTTP_AUTHORIZATION=authorization)
    assert client.get("/api/v1/auth/me").status_code == 200
    assert DeviceActivityDay.objects.filter(grant=grant, makerspace=None, platform="android").count() == 1
    before = list(DeviceActivityDay.objects.filter(grant=grant).order_by("pk").values())
    other = make_space("activity-refused")
    # APIClient credentials override per-request headers; replace the default
    # selection so this request really reaches authentication with the foreign ID.
    client.credentials(HTTP_AUTHORIZATION=authorization,
                       HTTP_X_MAKERSPACE_ID=str(other.pk))
    response = client.post("/api/v1/integrations/push/devices", {
        "token": "t" * 64, "provider": "fcm", "environment": "development",
    }, format="json")
    assert response.status_code == 403
    assert response.wsgi_request.headers["X-Makerspace-Id"] == str(other.pk)
    assert not DeviceActivityDay.objects.filter(makerspace=other).exists()
    assert list(DeviceActivityDay.objects.filter(grant=grant).order_by("pk").values()) == before


@pytest.mark.parametrize("error,outcome", [
    (None, "sent"), (AttestationRejected("private attestation"), "failed"),
    (AttestationUnavailable("private service"), "skipped"), (RuntimeError("private proof"), "failed"),
])
def test_every_attestation_outcome_has_one_identifier_free_fact(monkeypatch, error, outcome):
    from apps.accounts.attestation import verify_attestation
    monkeypatch.setattr("apps.accounts.attestation.readiness_mode", lambda *a: "external")
    monkeypatch.setattr("apps.accounts.attestation._verify_attestation", Mock(
        side_effect=error, return_value=VerifiedAttestation("private subject"),
    ))
    challenge = SimpleNamespace(platform="android", signing_identity="private app", environment="production")
    if error:
        with pytest.raises(type(error)):
            verify_attestation(challenge, "private challenge", {"proof": "private token"})
    else:
        verify_attestation(challenge, "private challenge", {"proof": "private token"})
    row = AttestationVerificationLog.objects.get()
    assert (row.platform, row.mode, row.outcome) == ("android", "external", outcome)
    assert {f.name for f in row._meta.concrete_fields} == {"id", "platform", "mode", "outcome", "created_at"}


def test_explicit_development_attestation_does_not_contact_a_provider(settings, monkeypatch):
    from apps.accounts.attestation import verify_attestation
    settings.DEBUG = True
    settings.DEVICE_ATTESTATION_DEV_INSECURE = True
    monkeypatch.setattr("apps.accounts.attestation.readiness_mode", Mock(side_effect=AssertionError("provider must not be resolved")))
    challenge = SimpleNamespace(platform="android", signing_identity="private app", environment="development")
    assert verify_attestation(challenge, "private challenge", {"type": "development"}).subject == "development"
    assert AttestationVerificationLog.objects.get().mode == "development_insecure"


@pytest.mark.parametrize("result,status", [(True, "sent"), (False, "failed"), (None, "skipped"), (RuntimeError("+15555551212"), "failed")])
def test_sms_outcomes_have_no_phone_body_or_exception_text(monkeypatch, caplog, result, status):
    from apps.integrations.sms import send_sms
    provider = None if result is None else SimpleNamespace(send=Mock(
        side_effect=result if isinstance(result, Exception) else None, return_value=result,
    ))
    monkeypatch.setattr("apps.integrations.sms.get_sms_provider", lambda: provider)
    assert send_sms(to="+15555551212", body="OTP 123456") is (status == "sent")
    row = SmsSendLog.objects.get()
    assert (row.status, row.provider_source, row.purpose, row.makerspace_id) == (status, "platform", "authentication", None)
    assert {f.name for f in row._meta.concrete_fields} == {"id", "makerspace", "purpose", "provider_source", "status", "created_at"}
    assert "+15555551212" not in caplog.text and "123456" not in caplog.text
