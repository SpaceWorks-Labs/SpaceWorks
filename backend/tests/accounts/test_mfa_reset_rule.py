"""S-A: the MFA-reset rule (#66): superadmin always; a Space Manager only inside the rule."""

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import mfa_reset
from apps.accounts.mfa_policy import credential, stamp
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_mfa_grace import StaffMfaGrace
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.reauthentication import versions
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import grant_staff_role, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.tenant_rls.conftest import probe  # noqa: F401 - real narrow-role RLS fixture

pytestmark = pytest.mark.django_db
PASSWORD = "Reset rule password 19!"
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


@pytest.fixture
def spaces():
    return (Makerspace.objects.create(name="Reset A", slug="reset-a"),
            Makerspace.objects.create(name="Reset B", slug="reset-b"))


def with_factors(user):
    enrolled(user, recovery_digests=["d1"])
    WebAuthnCredential.objects.create(user=user, credential_id=f"reset-{user.pk}", public_key=b"k", rp_id="localhost")
    return user


def manager_client(manager):
    enrolled(manager)
    stamp(manager, credential(manager), "totp")
    token = SpaceWorksRefreshToken.for_user(manager).access_token
    ReauthenticationSession.objects.update_or_create(session_id=token["sid"], defaults={
        "user": manager, "surface": token["surface"], "auth_time": timezone.now(), **versions(manager)})
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN=ORIGIN)
    return api


def reset_url(space, row):
    return f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/{row.pk}/mfa-reset"


def test_superadmin_always_and_everything_is_cleared(spaces):
    a, _b = spaces
    root = User.objects.create_superuser("reset-root", password=PASSWORD)
    target = with_factors(make_staff(a, username="reset-sm-target", password=PASSWORD))
    before = UserMFA.objects.get(user=target).version
    assert mfa_reset.reset(root, target, "Lost phone and keys", a) == "superadmin"
    row = UserMFA.objects.get(user=target)
    assert row.enabled_at is None and row.recovery_digests == [] and row.version != before
    assert not WebAuthnCredential.objects.filter(user=target).exists()
    assert StaffMfaGrace.objects.get(user=target).ends_at <= timezone.now()  # enrol again first
    entry = AuditLog.objects.get(action="auth.mfa_reset")
    assert entry.meta["rule"] == "superadmin" and entry.makerspace_id == a.pk


def test_space_manager_inside_the_rule_over_http(spaces):
    a, _b = spaces
    manager = make_staff(a, username="reset-manager", password=PASSWORD)
    target = with_factors(make_staff(a, username="reset-tech", password=PASSWORD, role_slug="inventory_manager"))
    row = MakerspaceMembership.staff_tracks.get(user=target, makerspace=a)
    response = manager_client(manager).post(reset_url(a, row), {"reason": "Lost authenticator"}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["rule"] == "space_manager"
    assert not WebAuthnCredential.objects.filter(user=target).exists()


def test_space_manager_refused_for_authority_elsewhere(spaces):
    a, b = spaces
    manager = make_staff(a, username="reset-manager-2", password=PASSWORD)
    target = make_staff(a, username="reset-two-spaces", password=PASSWORD, role_slug="inventory_manager")
    grant_staff_role(target, b, role_slug="inventory_manager")
    assert mfa_reset.rule_for(manager, target, a) is None
    row = MakerspaceMembership.staff_tracks.get(user=target, makerspace=a)
    response = manager_client(manager).post(reset_url(a, row), {"reason": "Lost authenticator"}, format="json")
    assert response.status_code == 403 and response.data["code"] == "mfa_reset_not_allowed"


def test_space_manager_refused_for_another_space_manager(spaces):
    a, _b = spaces
    manager = make_staff(a, username="reset-manager-3", password=PASSWORD)
    other = make_staff(a, username="reset-other-sm", password=PASSWORD)
    assert mfa_reset.rule_for(manager, other, a) is None
    with pytest.raises(mfa_reset.MfaResetNotAllowed):
        mfa_reset.reset(manager, other, "Not allowed here", a)


def test_space_manager_of_another_space_refused(spaces):
    a, b = spaces
    manager_b = make_staff(b, username="reset-manager-b", password=PASSWORD)
    target = make_staff(a, username="reset-a-only", password=PASSWORD, role_slug="inventory_manager")
    assert mfa_reset.rule_for(manager_b, target, a) is None
    assert mfa_reset.rule_for(manager_b, target, b) is None


def test_host_command(spaces):
    a, _b = spaces
    target = with_factors(make_staff(a, username="reset-host", password=PASSWORD))
    call_command("reset_mfa", target.username, reason="Host recovery")
    assert not UserMFA.objects.get(user=target).enabled_at
    assert AuditLog.objects.get(action="auth.mfa_reset").meta["rule"] == "host"


def test_readiness_lists_unenrolled_staff(spaces, capsys):
    a, _b = spaces
    make_staff(a, username="ready-not", password=PASSWORD, role_slug="inventory_manager")
    with_factors(make_staff(a, username="ready-yes", password=PASSWORD))
    call_command("staff_mfa_readiness")
    out = capsys.readouterr().out
    assert "ready-not" in out and "ready-yes" not in out


@pytest.mark.parametrize("foreign_staff", [False, True], ids=["local-authority-only", "foreign-staff-authority"])
def test_reset_rule_sees_all_authority_and_restores_the_outer_tenant_binding(spaces, probe, foreign_staff):
    """A tenant-bound request must not hide authority that makes an MFA reset unsafe."""
    from apps.tenant_rls.context import current, tenant_context

    assert probe.failed == {}
    a, b = spaces
    manager = make_staff(a, username="reset-bound-manager", password=PASSWORD)
    target = make_staff(a, username="reset-bound-target", password=PASSWORD, role_slug="inventory_manager")
    if foreign_staff:
        grant_staff_role(target, b, role_slug="inventory_manager")
    before = current()
    expected_rule = None if foreign_staff else mfa_reset.RULE_SPACE_MANAGER
    with tenant_context(a.pk, label="mfa-reset-nested-regression") as outer:
        # Execute a real bound query first: the narrow role/GUC must already hide B.
        visible = MakerspaceMembership.staff_tracks.filter(user=target).values_list("makerspace_id", flat=True)
        assert list(visible) == [a.pk]
        assert current() is outer
        assert mfa_reset.rule_for(manager, target, a) == expected_rule
        assert current() is outer
        # The temporary open authority read must never leave later SQL unscoped.
        assert list(MakerspaceMembership.staff_tracks.filter(user=target).values_list("makerspace_id", flat=True)) == [a.pk]
        assert not MakerspaceMembership.staff_tracks.filter(user=target, makerspace=b).exists()
    assert current() is before


@pytest.mark.parametrize("rule", [mfa_reset.RULE_SUPERADMIN, mfa_reset.RULE_SPACE_MANAGER, mfa_reset.RULE_HOST])
def test_caller_supplied_rule_is_not_authority(spaces, rule):
    a, _ = spaces
    stranger = make_staff(a, username=f"reset-stranger-{rule}", password=PASSWORD, role_slug="inventory_manager")
    target = with_factors(make_staff(a, username=f"reset-victim-{rule}", password=PASSWORD,
                                     role_slug="inventory_manager"))
    with pytest.raises(mfa_reset.MfaResetNotAllowed):
        mfa_reset.reset(stranger, target, "Bypass attempt", a, rule=rule)
    assert UserMFA.objects.get(user=target).secret
    assert not AuditLog.objects.filter(action="auth.mfa_reset", target_id=str(target.pk)).exists()


def test_only_host_rule_is_accepted_without_an_actor(spaces):
    a, _ = spaces
    target = with_factors(make_staff(a, username="reset-actorless", password=PASSWORD))
    with pytest.raises(mfa_reset.MfaResetNotAllowed):
        mfa_reset.reset(None, target, "No actor", rule=mfa_reset.RULE_SUPERADMIN)
    assert mfa_reset.reset(None, target, "Host recovery", rule=mfa_reset.RULE_HOST) == mfa_reset.RULE_HOST
