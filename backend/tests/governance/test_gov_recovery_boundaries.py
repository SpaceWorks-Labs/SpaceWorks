"""Malformed input and concurrent disappearance keep recovery failures generic."""

from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetEnvelope, User
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import claim_pending_envelopes, prepare_delivery
from apps.accounts.throttles import PasswordResetEmailThrottle
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("payload", [{"email": []}, {"email": {}}, {"email": "valid@example.test", "context": []}, {"email": "valid@example.test", "context": "staff", "makerspace": {}}, ["invalid"]])
def test_invalid_payload_reaches_serializer_instead_of_crashing_throttle(monkeypatch, payload):
    monkeypatch.setattr("apps.accounts.views_password.email_enabled", lambda: True)
    response = APIClient().post(reverse("auth-forgot-password"), payload, format="json")
    assert response.status_code == 400
    assert not PasswordResetEnvelope.objects.exists()


@pytest.mark.parametrize("raw", [None, True, [], {}, ["email"]])
def test_unvalidated_email_types_do_not_crash_throttle(raw):
    assert PasswordResetEmailThrottle().get_cache_key(SimpleNamespace(data={"email": raw}), None) is None


def test_numeric_identifier_uses_same_budget_as_its_valid_string_form():
    throttle = PasswordResetEmailThrottle()
    assert throttle.get_cache_key(SimpleNamespace(data={"email": 123}), None) == throttle.get_cache_key(
        SimpleNamespace(data={"email": "123"}), None)


@pytest.mark.parametrize("origin", ["https://" + "x" * 600 + ".example", "http://["])
def test_member_recovery_does_not_persist_unbounded_or_malformed_origin(monkeypatch, origin):
    monkeypatch.setattr("apps.accounts.views_password.email_enabled", lambda: True)
    user = User.objects.create_user(username="gov-origin", email="gov-origin@example.test")
    response = APIClient().post(reverse("auth-forgot-password"), {"email": user.email},
        format="json", HTTP_ORIGIN=origin)
    assert response.status_code == 200
    assert PasswordResetEnvelope.objects.get(user=user).request_origin == ""


@pytest.mark.parametrize("operation", ["request", "confirm", "worker"])
def test_account_disappearing_between_lookup_and_lock_is_unavailable(monkeypatch, operation):
    user = User.objects.create_user(username="gov-disappeared", email="gone@example.test")
    request_password_reset(user.email)
    claim = claim_pending_envelopes(owner="stale-account")[0]

    def disappeared(*args, **kwargs):
        raise User.DoesNotExist

    monkeypatch.setattr("apps.accounts.credential_locks.lock_credentials", disappeared)
    if operation == "request":
        assert request_password_reset(user.email) is None
    elif operation == "confirm":
        with pytest.raises(ValidationError, match="Invalid or expired"):
            confirm_password_reset(user.email, "123456", "Governance password 459!")
    else:
        assert prepare_delivery(claim) == "discarded"


@pytest.mark.parametrize("kind", ["staff", "platform"])
def test_username_only_account_confirmation_has_generic_failure(kind):
    if kind == "staff":
        space = Makerspace.objects.create(name="Username only", slug="gov-username-only")
        user = make_staff(space, username="gov-no-email-staff")
        payload = {"context": kind, "makerspace": space.slug}
    else:
        user = User.objects.create_superuser(username="gov-no-email-platform")
        payload = {"context": kind}
    payload.update(email=user.username, code="123456", new_password="Governance password 819!")
    response = APIClient().post(reverse("auth-reset-password"), payload, format="json",
        HTTP_ORIGIN="http://localhost:5000")
    assert response.status_code == 400
    assert response.data == {"detail": "Invalid or expired verification code."}
    assert not PasswordResetEnvelope.objects.exists()
