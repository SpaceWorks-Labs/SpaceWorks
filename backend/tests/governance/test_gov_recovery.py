"""Recovery is account-owned and never grants a different account surface."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import PasswordResetEnvelope, User
from apps.accounts.services_password_reset import request_password_reset, confirm_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes, prepare_delivery, finalize_delivery, drain_password_reset_envelopes,
)
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import grant_staff_role, make_staff
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db
ORIGIN = "https://staff.example.test"
PASSWORD = "Starting-governance-password-527!"
NEW_PASSWORD = "Recovered-governance-password-419!"


@pytest.fixture(autouse=True)
def configuration(settings, monkeypatch):
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    settings.PUBLIC_APP_BASE_URL = ORIGIN
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.platform_email_configured", lambda: True)
    cache.clear()


def accounts():
    """One account per person (decision 63; uniq_person_email): ``staff`` is a person holding
    staff-track rows in two spaces, ``member`` another person, ``platform`` the superadmin."""
    space = Makerspace.objects.create(name="Recovery A", slug="gov-recovery-a")
    other = Makerspace.objects.create(name="Recovery B", slug="gov-recovery-b")
    staff = make_staff(space, username="gov-worker", email="gov-worker@example.test", password=PASSWORD)
    grant_staff_role(staff, other)
    member = User.objects.create_user("gov-member", email="gov-member@example.test", password=PASSWORD)
    platform = User.objects.create_superuser("gov-platform", email="gov-platform@example.test", password=PASSWORD)
    return space, staff, member, platform


def issue(user, *, context="platform", origin=ORIGIN):
    """Recovery has only the person (member) and platform contexts; the release-1 staff
    context and its makerspace slug are gone (decisions 63/66)."""
    kwargs = {"context": context, "origin": origin}
    envelope = request_password_reset(user.username, **kwargs)
    assert envelope is not None
    claim = claim_pending_envelopes()[0]
    attempt = prepare_delivery(claim)
    assert not isinstance(attempt, str) and attempt is not None
    assert finalize_delivery(claim, delivered=True)
    return attempt.code, kwargs


@pytest.mark.parametrize("kind", [
    pytest.param("staff", marks=pytest.mark.skip(reason="Decisions 63/66: one account per person - there is no staff recovery context; a staff person recovers through the person (member) flow")),
    "platform",
])
def test_context_reset_revokes_sessions_and_keeps_same_email_accounts_independent(kind):
    space, staff, member, platform = accounts()
    target = platform
    refresh = SpaceWorksRefreshToken.for_user(target)
    code, kwargs = issue(target, context=kind)
    assert confirm_password_reset(target.username, code, NEW_PASSWORD, **kwargs).pk == target.pk
    target.refresh_from_db()
    assert target.check_password(NEW_PASSWORD) and not target.must_change_password
    assert target.credential_generation == 1
    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
    for other in (member, staff):
        other.refresh_from_db()
        assert other.check_password(PASSWORD)
    with pytest.raises(serializers.ValidationError):
        confirm_password_reset(target.email, code, NEW_PASSWORD, **kwargs)


@pytest.mark.parametrize("context,slug,identifier,origin", [
    ("platform", None, "unknown", ORIGIN),
    ("platform", None, "gov-worker", ORIGIN),
    ("platform", None, "gov-worker@example.test", ORIGIN),
    ("platform", None, "gov-platform", "https://evil.test"),
])
def test_invalid_namespace_or_origin_has_same_acknowledgement_without_envelope(context, slug, identifier, origin):
    accounts()
    payload = {"context": context, "email": identifier}
    if slug:
        payload["makerspace"] = slug
    response = APIClient().post("/api/v1/auth/forgot-password", payload, format="json", HTTP_ORIGIN=origin)
    assert response.status_code == 200
    assert response.data == {"detail": "If an account exists for that email, a reset link has been sent."}
    assert not PasswordResetEnvelope.objects.exists()


def test_staff_context_is_refused_at_the_serializer_with_no_envelope():
    """Decisions 63/66: the release-1 staff recovery context no longer exists."""
    accounts()
    response = APIClient().post("/api/v1/auth/forgot-password",
        {"context": "staff", "makerspace": "gov-recovery-a", "email": "gov-worker@example.test"},
        format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 400 and "context" in response.data
    assert not PasswordResetEnvelope.objects.exists()


@pytest.mark.parametrize("phase", ["request", "worker"])
def test_platform_email_is_required_at_both_boundaries(monkeypatch, phase):
    _, _, _, platform = accounts()
    if phase == "request":
        monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: False)
        assert request_password_reset(platform.email, context="platform", origin=ORIGIN) is None
        assert not PasswordResetEnvelope.objects.exists()
    else:
        request_password_reset(platform.email, context="platform", origin=ORIGIN)
        monkeypatch.setattr("apps.accounts.services_password_reset_drain.platform_email_configured", lambda: False)
        assert prepare_delivery(claim_pending_envelopes()[0]) == "undeliverable"


_TENANT_GONE = "Decisions 63/66: recovery is account-level (person or platform); tenant membership, archive and migration gates no longer apply to it"


@pytest.mark.parametrize("change", [
    "restricted", "suspended", "inactive",
    pytest.param("revoked", marks=pytest.mark.skip(reason=_TENANT_GONE)),
    pytest.param("archived", marks=pytest.mark.skip(reason=_TENANT_GONE)),
    pytest.param("migrating", marks=pytest.mark.skip(reason=_TENANT_GONE)),
])
@pytest.mark.parametrize("phase", ["request", "worker", "confirm"])
def test_live_boundaries_recheck_account_and_tenant(change, phase):
    space, _, _, staff = accounts()  # the platform account: the only recoverable non-person context
    platform = staff
    kwargs = {"context": "platform", "origin": ORIGIN}
    if phase == "worker":
        request_password_reset(staff.email, **kwargs)
        claim = claim_pending_envelopes()[0]
    elif phase == "confirm":
        code, _ = issue(staff)
    if change in {"restricted", "suspended"}:
        User.objects.filter(pk=staff.pk).update(access_status=change)
    elif change == "inactive":
        User.objects.filter(pk=staff.pk).update(is_active=False)
    elif change == "revoked":
        staff.makerspace_memberships.update(status="revoked")
    elif change == "archived":
        Makerspace.objects.filter(pk=space.pk).update(archived_at=timezone.now())
    else:
        from apps.tenant_migration.models_source_gate import SourceMigrationGate
        close_gate(space, platform, state=SourceMigrationGate.State.DRAINING)
    if phase == "request":
        assert request_password_reset(staff.email, **kwargs) is None
    elif phase == "worker":
        assert prepare_delivery(claim) == "discarded"
    else:
        with pytest.raises(serializers.ValidationError):
            confirm_password_reset(staff.email, code, NEW_PASSWORD, **kwargs)
    staff.refresh_from_db()
    assert staff.check_password(PASSWORD)


def test_context_tenant_attempt_budget_expiry_and_generation_fences():
    _, _, _, staff = accounts()
    code, kwargs = issue(staff)
    for wrong in ({"context": "member", "origin": ORIGIN},
                  {**kwargs, "origin": "https://evil.test"}):
        with pytest.raises(serializers.ValidationError):
            confirm_password_reset(staff.username, code, NEW_PASSWORD, **wrong)
    for _ in range(5):
        with pytest.raises(serializers.ValidationError):
            confirm_password_reset(staff.username, "wrong-code", NEW_PASSWORD, **kwargs)
    with pytest.raises(serializers.ValidationError):
        confirm_password_reset(staff.username, code, NEW_PASSWORD, **kwargs)
    row = PasswordResetEnvelope.objects.get(user=staff)
    row.attempts = 0
    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save()
    with pytest.raises(serializers.ValidationError):
        confirm_password_reset(staff.username, code, NEW_PASSWORD, **kwargs)
    row.expires_at = timezone.now() + timedelta(minutes=10)
    row.save()
    User.objects.filter(pk=staff.pk).update(credential_generation=1)
    with pytest.raises(serializers.ValidationError):
        confirm_password_reset(staff.username, code, NEW_PASSWORD, **kwargs)


@pytest.mark.skip(reason="Decisions 63/66: no staff recovery context - recovery mail is sent from the person/platform flows and the platform reset page only (password_reset_context.reset_destination)")
def test_trusted_verified_tenant_mail_has_otp_and_page_without_bearer(monkeypatch):
    space, staff, _, _ = accounts()
    space.frontend_domain = "verified.example.test"
    space.frontend_domain_status = "verified"
    space.save()
    request_password_reset(staff.email, context="staff", makerspace=space.slug, origin="https://verified.example.test")
    sent = []
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.send_password_reset_otp",
                        lambda *args, **kwargs: sent.append((args, kwargs)) or 1)
    assert drain_password_reset_envelopes()["issued"] == 1
    args, details = sent[0]
    assert len(args[1]) == 6 and args[1].isdigit()
    assert details["reset_url"] == "https://verified.example.test/admin/reset-password"
    assert details["account_label"] == space.name
    assert args[1] not in details["reset_url"] and "token=" not in details["reset_url"]


@pytest.mark.skip(reason="Decisions 63/66: staff login (context=staff + makerspace slug) and staff recovery are retired; the person login MFA path is covered by the login-security tests")
def test_reset_preserves_enrolment_and_invalidates_pre_reset_mfa(settings):
    from cryptography.fernet import Fernet
    from apps.accounts import mfa_challenges
    from apps.accounts.models_mfa import UserMFA
    from tests.accounts.mfa_helpers import enrolled
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space, staff, _, _ = accounts()
    enrolled(staff)
    factor = UserMFA.objects.get(user=staff)
    pending = mfa_challenges.start(staff, context={"surface": "staff_api", "origin": ORIGIN})
    code, kwargs = issue(staff, space=space)
    confirm_password_reset(staff.email, code, NEW_PASSWORD, **kwargs)
    factor.refresh_from_db()
    assert factor.enabled_at is not None
    client = APIClient()
    assert client.post("/api/v1/auth/mfa/verify", {"challenge": pending["challenge"], "code": "000000"},
                       format="json", HTTP_ORIGIN=ORIGIN).status_code == 401
    result = client.post("/api/v1/auth/login", {"context": "staff", "makerspace": space.slug,
                         "username": staff.email, "password": NEW_PASSWORD}, format="json", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 200 and result.data["mfa_required"]


@pytest.mark.skip(reason="Feature not in release 0.12.0: apps.makerspaces.staff_retirement.retire_staff_accounts (separate staff accounts retired by #63/#66)")
def test_retired_staff_cannot_request_recovery():
    from django.db import transaction
    from apps.makerspaces.staff_retirement import retire_staff_accounts
    space, staff, _, _ = accounts()
    old_username, old_email = staff.username, staff.email
    with transaction.atomic():
        retire_staff_accounts(space)
        staff.makerspace_memberships.all().delete()
    for identifier in (old_username, old_email):
        assert request_password_reset(identifier, context="staff", makerspace=space.slug, origin=ORIGIN) is None
    assert not PasswordResetEnvelope.objects.exists()


@pytest.mark.skip(reason="Decisions 63/66: staff recovery envelopes no longer exist (an inert shell's envelope is history); the staff_makerspace credential path now concerns shells only")
def test_staff_recovery_envelope_is_registered_for_sealed_tenant_slice():
    from apps.backup.main_projection_registry import table_rules, sovereign_q, RowDisposition
    from apps.backup.staff_shells import STAFF_CREDENTIAL_PATHS
    space, staff, _, _ = accounts()
    request_password_reset(staff.email, context="staff", makerspace=space.slug, origin=ORIGIN)
    rule = next(rule for rule in table_rules() if rule.model is PasswordResetEnvelope)
    assert rule.disposition == RowDisposition.COPY_TO_SLICE
    assert STAFF_CREDENTIAL_PATHS["accounts.PasswordResetEnvelope"] == "user__staff_makerspace"
    assert PasswordResetEnvelope.objects.filter(sovereign_q(rule.predicate, [space.pk])).count() == 1
