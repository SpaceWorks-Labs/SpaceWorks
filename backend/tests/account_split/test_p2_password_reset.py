"""Recovery owns a member account, never a shared contact address."""

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus, User
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes, drain_password_reset_envelopes, prepare_delivery,
)
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff
from tests.accounts.password_reset_helpers import issue_otp

pytestmark = pytest.mark.django_db
PASSWORD = "Starting-password-419!"
NEW_PASSWORD = "Recovered-password-771!"


def accounts_sharing_email(email="shared-recovery@example.test"):
    member = User.objects.create_user(username="recovery-member", email=email, password=PASSWORD)
    platform = User.objects.create_superuser(username="recovery-platform", email=email, password=PASSWORD) if False else User.objects.create_superuser(username="recovery-platform", email="recovery-platform@example.test", password=PASSWORD)
    staff = []
    for slug in ("recovery-a", "recovery-b"):
        space = Makerspace.objects.create(name=slug, slug=slug)
        staff.append(make_staff(space, username=f"staff-{slug}", email=f"staff-{slug}@example.test", password=PASSWORD))
    return member, *staff, platform


def test_shared_email_recovers_only_the_member(monkeypatch):
    member, *other_accounts = accounts_sharing_email()
    refreshes = {user.pk: SpaceWorksRefreshToken.for_user(user) for user in [member, *other_accounts]}
    code = issue_otp(member, monkeypatch)
    envelope = PasswordResetEnvelope.objects.get()
    assert envelope.user_id == member.pk
    assert confirm_password_reset(member.email, code, NEW_PASSWORD).pk == member.pk
    assert BlacklistedToken.objects.filter(token__jti=refreshes[member.pk]["jti"]).exists()
    for other in other_accounts:
        other.refresh_from_db()
        assert other.check_password(PASSWORD)
        assert not other.password_reset_envelopes.exists()
        assert not BlacklistedToken.objects.filter(token__jti=refreshes[other.pk]["jti"]).exists()


@pytest.mark.parametrize("kind", ["platform", "unknown"])  # a staff-track holder is a person (U-A1) and may reset
def test_nonmember_requests_are_generic_without_a_queue_row_or_mail(monkeypatch, kind):
    email = "nonmember-reset@example.test"
    if kind == "staff":
        space = Makerspace.objects.create(name="Recovery", slug="nonmember-recovery")
        make_staff(space, username="staff-reset", email=email, password=PASSWORD)
    elif kind == "platform":
        User.objects.create_superuser(username="platform-reset", email=email, password=PASSWORD)
    sent = []
    monkeypatch.setattr("apps.accounts.views_password.email_enabled", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.email_enabled", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.send_password_reset_otp",
                        lambda *args, **kwargs: sent.append(args) or 1)
    response = APIClient().post(reverse("auth-forgot-password"), {"email": email}, format="json")
    assert response.status_code == 200
    assert response.json() == {"detail": "If an account exists for that email, a reset link has been sent."}
    assert not PasswordResetEnvelope.objects.exists()
    assert drain_password_reset_envelopes()["claimed"] == 0
    assert sent == []


def test_legacy_links_cannot_reset_staff_or_platform_even_with_shared_email():
    member, *others = accounts_sharing_email()
    others = others[-1:]  # the platform account; staff-track holders are people (U-A1) and may reset
    responses = []
    for other in others:
        response = APIClient().post(reverse("auth-reset-password"), {
            "uid": urlsafe_base64_encode(force_bytes(other.pk)),
            "token": default_token_generator.make_token(other), "new_password": NEW_PASSWORD,
        }, format="json")
        responses.append((response.status_code, response.content))
        other.refresh_from_db()
        assert other.check_password(PASSWORD)
    assert len(set(responses)) == 1
    assert responses[0][0] == 400
    member.refresh_from_db()
    assert member.check_password(PASSWORD)


def test_worker_discards_nonmember_envelopes_without_minting_an_otp(monkeypatch):
    _, *others = accounts_sharing_email()
    others = others[-1:]  # platform only (U-A1: staff-track holders are people)
    for account in others:
        PasswordResetEnvelope.objects.create(
            user=account, context=account.account_kind, makerspace_id=account.staff_makerspace_id,
            email_normalized=account.email, email_fingerprint="f" * 64,
            digest="d" * 64, requested_at=timezone.now(),
        )
    def refuse_mint():
        raise AssertionError("Non-member recovery must never mint a secret")
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.generate_otp", refuse_mint)
    claims = claim_pending_envelopes()
    assert len(claims) == len(others)
    for claim in claims:
        assert prepare_delivery(claim) == PasswordResetEnvelopeStatus.DISCARDED
    assert not PasswordResetEnvelope.objects.filter(digest_is_live=True).exists()


def test_worker_never_rebinds_envelope_when_email_moves_to_another_member(monkeypatch):
    original = User.objects.create_user(username="original-reset", email="move@example.test", password=PASSWORD)
    envelope = request_password_reset(original.email)
    original.email = "new@example.test"
    original.save(update_fields=["email"])
    replacement = User.objects.create_user(username="replacement-reset", email="move@example.test", password=PASSWORD)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.email_enabled", lambda: True)
    claim = claim_pending_envelopes()[0]
    assert prepare_delivery(claim) == PasswordResetEnvelopeStatus.DISCARDED
    envelope.refresh_from_db()
    assert envelope.user_id == original.pk
    assert not replacement.password_reset_envelopes.exists()


def test_account_generation_change_invalidates_reset_even_without_password_change(monkeypatch):
    member = User.objects.create_user(username="generation-reset", email="gen@example.test", password=PASSWORD)
    code = issue_otp(member, monkeypatch)
    member.credential_generation += 1
    member.save(update_fields=["credential_generation"])
    with pytest.raises(serializers.ValidationError):
        confirm_password_reset(member.email, code, NEW_PASSWORD)
    member.refresh_from_db()
    assert member.check_password(PASSWORD)


def test_recovery_uniqueness_is_per_account_and_requires_an_account():
    member = User.objects.create_user(username="unique-reset", email="unique@example.test")
    envelope = request_password_reset(member.email)
    fields = {"email_normalized": "another@example.test", "email_fingerprint": "f" * 64,
              "digest": "d" * 64, "requested_at": envelope.requested_at}
    with pytest.raises(IntegrityError), transaction.atomic():
        PasswordResetEnvelope.objects.create(user=member, **fields)
    with pytest.raises(IntegrityError), transaction.atomic():
        PasswordResetEnvelope.objects.create(**fields)


def test_cutover_invalidates_old_sessions_refresh_and_unbound_reset_rows():
    member = User.objects.create_user(username="cutover-reset", email="cutover@example.test")
    refresh = SpaceWorksRefreshToken.for_user(member)
    session = SessionStore()
    session["_auth_user_id"] = str(member.pk)
    session.save()
    request_password_reset(member.email)
    migration = importlib.import_module("apps.accounts.migrations.0035_as_p2_password_reset")
    migration.invalidate_legacy_authentication(apps, SimpleNamespace(connection=connection))
    assert not Session.objects.filter(session_key=session.session_key).exists()
    assert not PasswordResetEnvelope.objects.exists()
    outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
    assert BlacklistedToken.objects.filter(token=outstanding).exists()
