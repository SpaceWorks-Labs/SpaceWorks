"""Equal-work reset requests and the one-lookup, one-send phone restore seam."""

from unittest.mock import Mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts import services_password_reset_drain as drain
from apps.accounts.account_restore_phone import confirm_phone
from apps.accounts.models import User, PasswordResetEnvelope
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_phone_login import start_login
from tests.accounts.restore_helpers_m1d import PASSWORD, archive, email_proof, restore_config
from tests.accounts.test_support_m1d import account, m1d_config
from tests.accounts.test_phone_auth_p8 import sms_on, code_from, NUMBER, OTHER_NUMBER, LOGIN_START

pytestmark = pytest.mark.django_db


def phone_user(*, archived=True):
    user = account()
    user.email = ""
    user.phone_e164 = NUMBER
    user.save()
    User.objects.filter(pk=user.pk).update(phone_verified_at=timezone.now())
    user.refresh_from_db()
    return archive(user) if archived else user


def phone_data(code, **extra):
    return {"phone": NUMBER, "code": code, "delivery": "web", "client_platform": "web",
            "new_password": PASSWORD, **extra}


def test_reset_request_active_archived_unknown_has_same_acknowledgement_without_delivery(monkeypatch):
    active, archived = account(), archive()
    send = Mock(side_effect=AssertionError("no delivery on request"))
    monkeypatch.setattr(drain, "send_password_reset_otp", send)
    monkeypatch.setattr(drain, "send_restore_link", send)
    responses = []
    for email in (active.email, archived.email, "unknown-restore@example.test"):
        response = APIClient().post("/api/v1/auth/forgot-password", {"email": email}, format="json")
        responses.append((response.status_code, response.content))
    assert len(set(responses)) == 1 and responses[0][0] == 200
    # T's queue is account-bound: unknown identifiers never acquire a row.
    assert PasswordResetEnvelope.objects.count() == 2
    assert set(PasswordResetEnvelope.objects.values_list("user_id", flat=True)) == {active.pk, archived.pk}
    assert not PasswordResetEnvelope.objects.filter(digest_is_live=True).exists()
    send.assert_not_called()


def test_existing_worker_chooses_exactly_one_correct_mail_for_active_archived_unknown(monkeypatch):
    active, archived = account(), archive()
    reset_send, restore_send = Mock(return_value=1), Mock(return_value=1)
    monkeypatch.setattr(drain, "send_password_reset_otp", reset_send)
    monkeypatch.setattr(drain, "send_restore_link", restore_send)
    for email in (active.email, archived.email, "unknown-restore@example.test"):
        request_password_reset(email)
    assert drain.drain_password_reset_envelopes()["issued"] == 2
    assert reset_send.call_count == restore_send.call_count == 1
    assert reset_send.call_args.args[0] == active.email
    assert restore_send.call_args.args[0] == archived.email
    assert len(restore_send.call_args.args[1]) >= 48
    assert drain.drain_password_reset_envelopes()["claimed"] == 0
    assert reset_send.call_count == restore_send.call_count == 1


def test_restore_mail_uses_fragment_secret_and_never_persists_body(settings, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit
    from apps.accounts.account_restore_email import send_restore_link
    settings.PUBLIC_APP_BASE_URL = "https://members.example.test"
    dispatch = Mock(return_value=SimpleNamespace(status="sent", Status=SimpleNamespace(SENT="sent")))
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", dispatch)
    assert send_restore_link("member@example.test", "secret-token")
    values = dispatch.call_args.kwargs
    assert values["persist_body"] is False and values["sync"] is True
    assert values["connection"] == "platform"
    link = next(line for line in values["text_body"].splitlines() if line.startswith("https://"))
    url = urlsplit(link)
    assert url.path == "/account/restore" and not url.query
    assert parse_qs(url.fragment) == {"email": ["member@example.test"], "token": ["secret-token"]}


def test_archived_mail_failure_is_terminal_and_worker_never_sends_twice(monkeypatch):
    user = archive()
    sender = Mock(side_effect=OSError("mail unavailable"))
    monkeypatch.setattr(drain, "send_restore_link", sender)
    request_password_reset(user.email)
    assert drain.drain_password_reset_envelopes()["terminal"] == 1
    row = PasswordResetEnvelope.objects.get(user=user)
    assert row.status == "undeliverable" and not row.digest_is_live
    assert drain.drain_password_reset_envelopes()["claimed"] == 0 and sender.call_count == 1


def test_restore_token_cannot_be_redeemed_at_reset_endpoint():
    user = archive()
    with pytest.raises(ValidationError):
        confirm_password_reset(user.email, email_proof(user), PASSWORD)
    user.refresh_from_db()
    assert not user.is_active


def test_signup_is_unchanged_and_does_not_send_restore_mail(monkeypatch):
    user = archive()
    send = Mock()
    monkeypatch.setattr(drain, "send_restore_link", send)
    result = APIClient().post("/api/v1/auth/member-sign-up", {
        "display_name": "Another signup", "email": user.email, "password": PASSWORD,
    }, format="json")
    assert result.status_code == 200
    user.refresh_from_db()
    assert not user.is_active and user.deletion_requested_at
    assert not PasswordResetEnvelope.objects.exists()
    send.assert_not_called()


@pytest.mark.parametrize("archived", [False, True])
def test_phone_active_archived_unknown_uniform_start_one_lookup_one_send(archived, sms_on):
    user = phone_user(archived=archived)
    with CaptureQueriesContext(connection) as queries:
        known = APIClient().post(LOGIN_START, {"phone": NUMBER}, format="json")
    # Later API requests reset Django's query log; freeze this request's capture.
    known_queries = list(queries)
    unknown = APIClient().post(LOGIN_START, {"phone": OTHER_NUMBER}, format="json")
    cooled = APIClient().post(LOGIN_START, {"phone": NUMBER}, format="json")
    assert known.status_code == unknown.status_code == cooled.status_code == 200
    assert known.content == unknown.content == cooled.content
    assert len(sms_on) == 1
    assert sum('FROM "accounts_user"' in query["sql"] for query in known_queries) == 1
    row = PhoneVerificationChallenge.objects.get(user=user)
    assert row.purpose == ("restore" if archived else "login")
    assert bool(row.credential_fingerprint) == archived
    assert ("account restore" in sms_on[0]["body"]) == archived


def test_phone_restore_requires_new_password_and_never_mints_a_session(sms_on):
    user = phone_user()
    start_login(NUMBER)
    result = APIClient().post("/api/v1/auth/account/restore/phone", phone_data(code_from(sms_on)), format="json")
    assert result.status_code == 200 and not result.cookies and "access" not in result.data
    user.refresh_from_db()
    assert user.is_active and user.check_password(PASSWORD)
    with pytest.raises(ValidationError):
        confirm_phone(phone_data(code_from(sms_on)))


@pytest.mark.parametrize("change", ["phone", "generation", "deadline"])
def test_phone_restore_rechecks_identifier_authority_and_deadline(change, sms_on):
    user = phone_user()
    start_login(NUMBER)
    values = {"phone": {"phone_e164": OTHER_NUMBER}, "generation": {"credential_generation": user.credential_generation + 1},
              "deadline": {"deletion_purge_after": timezone.now()}}
    User.objects.filter(pk=user.pk).update(**values[change])
    with pytest.raises(ValidationError):
        confirm_phone(phone_data(code_from(sms_on)))
    assert PhoneVerificationChallenge.objects.get(user=user).consumed_at


def test_phone_wrong_attempts_commit_and_restore_codes_never_login(sms_on):
    user = phone_user()
    start_login(NUMBER)
    correct = code_from(sms_on)
    wrong = "000000" if correct != "000000" else "111111"
    for count in range(1, 6):
        with pytest.raises(ValidationError):
            confirm_phone(phone_data(wrong))
        assert PhoneVerificationChallenge.objects.get(user=user).failed_attempts == count
    with pytest.raises(ValidationError):
        confirm_phone(phone_data(correct))
    from apps.accounts.services_phone_login import confirm_login
    with pytest.raises(ValidationError):
        confirm_login(NUMBER, correct)


def test_archived_email_account_does_not_get_phone_restore_otp(sms_on):
    user = account()
    user.phone_e164 = NUMBER
    user.save()
    User.objects.filter(pk=user.pk).update(phone_verified_at=timezone.now())
    user.refresh_from_db()
    archive(user)
    assert start_login(NUMBER) is None and sms_on == []


@pytest.mark.parametrize("tamper", ["foreign", "expired", "wrong_platform", "provider_failure", "none"])
def test_phone_restore_device_binding_and_consumption(settings, monkeypatch, sms_on, tamper):
    from apps.accounts.attestation import AttestationUnavailable
    from apps.accounts.services_phone_device import PhoneDeviceError
    from tests.accounts.native_helpers_m1d import configure_apple
    from tests.accounts.test_social_first_grant import issue_challenge
    from tests.accounts.native_helpers_m1d import mock_attestation
    configure_apple(settings)
    user = phone_user()
    raw = issue_challenge(APIClient())
    start_login(NUMBER, delivery="device", client_platform="ios", challenge=raw)
    otp = PhoneVerificationChallenge.objects.get(user=user)
    supplied = issue_challenge(APIClient()) if tamper == "foreign" else raw
    if tamper == "expired":
        type(otp.attestation_challenge).objects.filter(pk=otp.attestation_challenge_id).update(expires_at=timezone.now())
    mock_attestation(monkeypatch, raw)
    if tamper == "provider_failure":
        monkeypatch.setattr("apps.accounts.attestation.verify_attestation", Mock(side_effect=AttestationUnavailable("offline")))
    data = phone_data(code_from(sms_on), delivery="device", challenge=supplied, attestation={"assertion": "opaque"},
                      client_platform="android" if tamper == "wrong_platform" else "ios")
    if tamper == "none":
        confirm_phone(data)
        user.refresh_from_db()
        assert user.is_active
    else:
        with pytest.raises(PhoneDeviceError):
            confirm_phone(data)
    otp.refresh_from_db()
    assert otp.consumed_at
