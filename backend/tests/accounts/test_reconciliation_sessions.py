"""Reconciled identity snapshots and account-wide revocation across all account kinds."""

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.account_deletion import preview, request_deletion
from apps.accounts.account_restore import recovery_eligible, restorable
from apps.accounts.credential_locks import lock_token_issuance
from apps.accounts.credential_revocation import revoke_account_sessions
from apps.accounts.models import User
from apps.accounts.services_device_grants import authority_for_login, DeviceSuperadminNotSupported
from apps.accounts.session_issuance import lock_session_user
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
PASSWORD = "Reconciled-password-729!"


def principal(kind, *, username=None, email=None):
    email = email or f"{username or kind}-reconciliation@example.test"
    if kind == "staff":
        return make_staff(make_space(username or "session-staff"), username=username or "session-staff",
                          password=PASSWORD, email=email, role_slug="inventory_manager")
    return User.objects.create_user(username=username or "session-" + kind, password=PASSWORD,
        email=email, account_kind=kind, is_superuser=kind == "platform",
        role="superadmin" if kind == "platform" else "requester")


@pytest.mark.parametrize("kind", ["member", "staff", "platform"])
@pytest.mark.parametrize("lock", [lock_session_user, lock_token_issuance])
@pytest.mark.parametrize("change", ["password", "generation"])
def test_every_issuer_refuses_stale_proved_credentials(kind, lock, change):
    user = principal(kind)
    fresh = User.objects.get(pk=user.pk)
    if change == "password":
        fresh.set_password("A-different-password-348!")
        fresh.save(update_fields=["password"])
    else:
        User.objects.filter(pk=user.pk).update(credential_generation=user.credential_generation + 1)
    with transaction.atomic(), pytest.raises(AuthenticationFailed):
        lock(user)


def test_restore_epoch_fences_an_in_flight_pre_archive_login():
    user = principal("member")
    User.objects.filter(pk=user.pk).update(account_restored_at=timezone.now())
    with pytest.raises(AuthenticationFailed):
        SpaceWorksRefreshToken.for_user(user)


@pytest.mark.parametrize("kind", ["member", "staff", "platform"])
def test_tokens_bind_account_kind_generation_and_only_staff_tenant(kind):
    user = principal(kind)
    token = SpaceWorksRefreshToken.for_user(user)
    # U-A1: a staff-track holder is a person; only platform accounts carry their own kind.
    assert token["kind"] == ("platform" if kind == "platform" else "person")
    assert token["credential_generation"] == user.credential_generation
    assert token.get("makerspace") == user.staff_makerspace_id
    assert token["surface"] == ("platform" if kind == "platform" else "member")


@pytest.mark.parametrize("kind", ["platform"])  # a staff-track holder IS a person (U-A1) and may recover/delete
def test_member_lifecycle_refuses_nonmember_principals_before_proofs(kind):
    from types import SimpleNamespace
    user = principal(kind)
    assert not recovery_eligible(user) and not restorable(user)
    for operation in (preview, request_deletion):
        with pytest.raises(PermissionDenied):
            operation(SimpleNamespace(user=user))
    user.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is None


def test_staff_device_provenance_requires_password_and_local_authenticator():
    user = principal("staff")
    space_id = MakerspaceMembership.staff_tracks.get(user=user).makerspace_id
    assert authority_for_login(user, login_method="password") == "member"  # no staff step-up asked
    with pytest.raises((AuthenticationFailed, PermissionDenied)):
        authority_for_login(user, login_method="password", staff_makerspace_id=space_id)
    user._mfa_provider_verified = True
    with pytest.raises((AuthenticationFailed, PermissionDenied)):
        authority_for_login(user, login_method="password", staff_makerspace_id=space_id)
    row, _ = enrolled(user)
    from apps.accounts import mfa_policy
    mfa_policy.stamp(user, row)
    # Decision Q12: staff authority is a step-up after ANY primary login method, proven by a real second factor.
    for method in ("password", "phone", "social"):
        assert authority_for_login(user, login_method=method, staff_makerspace_id=space_id) == "staff"
    assert authority_for_login(principal("member"), login_method="social") == "member"
    with pytest.raises(DeviceSuperadminNotSupported):
        authority_for_login(principal("platform"), login_method="password")


def test_account_revocation_preserves_other_kinds_sharing_the_same_contact():
    member, staff, platform = (principal(kind) for kind in ("member", "staff", "platform"))
    tokens = {user.pk: SpaceWorksRefreshToken.for_user(user) for user in (member, staff, platform)}
    revoke_account_sessions(member)
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    for user in (staff, platform):
        user.refresh_from_db()
        assert user.credential_generation == 0
        assert OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True).exists()
        tokens[user.pk].check_blacklist()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens[member.pk].access_token}")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_native_password_resolution_honors_explicit_kind_and_fixed_tenant():
    from apps.accounts.services_device_login import authenticate_native
    member, staff = principal("member"), principal("staff")
    request = APIRequestFactory().post("/api/v1/auth/device/login")
    with transaction.atomic():
        assert authenticate_native(request, member.email, PASSWORD).pk == member.pk
        assert authenticate_native(request, staff.email, PASSWORD).pk == staff.pk  # one account per person
        assert authenticate_native(request, staff.username, PASSWORD).pk == staff.pk
        assert authenticate_native(request, principal("platform").email, PASSWORD) is None  # platform never holds a grant
