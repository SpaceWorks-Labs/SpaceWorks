"""S-A: staff MFA is mandatory (#62), independent of the platform switch; the staff gate."""

import pytest
from cryptography.fernet import Fernet
from rest_framework.exceptions import PermissionDenied

from apps.accounts import mfa_policy
from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.services_mfa import change
from apps.accounts.staff_identity import require_staff_mfa
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
PASSWORD = "Mandatory staff mfa 71!"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()


@pytest.fixture
def space():
    return Makerspace.objects.create(name="Policy", slug="policy")


def switch(on):
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"mfa_enabled": on})
    from django.core.cache import cache
    cache.clear()


def passkey(user, rp_id="localhost"):
    return WebAuthnCredential.objects.create(user=user, credential_id=f"cred-{user.pk}-{rp_id}",
                                             public_key=b"k", rp_id=rp_id)


def test_required_with_the_switch_off(space):
    switch(False)
    staff = make_staff(space, username="policy-staff", password=PASSWORD)
    member = User.objects.create_user("policy-member", password=PASSWORD)
    make_membership(member, space)
    root = User.objects.create_superuser("policy-root", password=PASSWORD)
    assert mfa_policy.required(staff) and not mfa_policy.required(member) and not mfa_policy.required(root)
    assert mfa_policy.available(staff) and not mfa_policy.available(member) and not mfa_policy.available()
    mfa_policy.assert_available(staff)
    with pytest.raises(PermissionDenied):
        mfa_policy.assert_available()


def test_no_bypass_for_a_required_person(space):
    switch(False)
    staff = make_staff(space, username="bypass-staff", password=PASSWORD)
    member = User.objects.create_user("bypass-member", password=PASSWORD)
    enrolled(staff)
    enrolled(member)
    assert mfa_policy.source_for(staff) == mfa_policy.NONE
    assert mfa_policy.source_for(member) == mfa_policy.BYPASS
    assert mfa_policy.needs_challenge(staff) and not mfa_policy.needs_challenge(member)


def _claims(row, source="verified", method="totp"):
    claims = {"mfa_source": source, "mfa_version": str(row.version)}
    if method:
        claims["mfa_method"] = method
    return claims


@pytest.mark.parametrize("source,method", [
    ("verified", None), ("provider", None), ("email_code", None), ("none", None), ("bypass", None),
])
def test_only_verified_factor_proof_satisfies_staff(space, source, method):
    staff = make_staff(space, username=f"proof-{source}", password=PASSWORD)
    row, _ = enrolled(staff)
    with pytest.raises(PermissionDenied) as refused:
        require_staff_mfa(staff, _claims(row, source, method))
    assert refused.value.detail["code"] == "mfa_required"


@pytest.mark.parametrize("method", ["totp", "recovery", "passkey"])
def test_verified_factor_methods_pass(space, method):
    staff = make_staff(space, username=f"pass-{method}", password=PASSWORD)
    row, _ = enrolled(staff)
    require_staff_mfa(staff, _claims(row, method=method))


def test_stale_version_refused(space):
    staff = make_staff(space, username="stale-version", password=PASSWORD)
    row, _ = enrolled(staff)
    claims = _claims(row)
    UserMFA.objects.filter(pk=row.pk).update(version="00000000-0000-0000-0000-000000000001")
    with pytest.raises(PermissionDenied):
        require_staff_mfa(staff, claims)


def test_passkey_counts_as_a_factor(space):
    staff = make_staff(space, username="passkey-only", password=PASSWORD)
    assert not mfa_policy.is_enrolled(staff)
    passkey(staff, rp_id="old.example.org")  # an orphaned RP ID still counts (no downgrade)
    assert mfa_policy.is_enrolled(staff) and not mfa_policy.totp_enabled(staff)
    assert mfa_policy.staff_factor_enrolled(staff)


def test_last_factor_refused_and_passkey_replaces_it(space):
    staff = make_staff(space, username="last-factor", password=PASSWORD)
    enrolled(staff, recovery_digests=["digest"])
    with pytest.raises(PermissionDenied) as refused:
        change(staff, PASSWORD, disable=True)
    assert refused.value.detail["code"] == "last_factor"
    passkey(staff)
    change(staff, PASSWORD, disable=True)
    row = UserMFA.objects.get(user=staff)
    assert row.enabled_at is None and row.recovery_digests == ["digest"]  # kept behind the passkey


def test_member_may_remove_their_only_factor(space):
    member = User.objects.create_user("member-optional", password=PASSWORD)
    enrolled(member)
    change(member, PASSWORD, disable=True)
    assert UserMFA.objects.get(user=member).enabled_at is None


def test_passkeys_disallowed_do_not_count_for_staff(space):
    from apps.makerspaces.models_security import MakerspaceSecurityPolicy
    staff = make_staff(space, username="disallowed", password=PASSWORD)
    row, _ = enrolled(staff)
    passkey(staff)
    policy = MakerspaceSecurityPolicy.objects.create(makerspace=space)
    # Fixture write: the guarded save keeps policy values to the security service.
    MakerspaceSecurityPolicy.objects.filter(pk=policy.pk).update(values={"security.passkeys_allowed": False})
    with pytest.raises(PermissionDenied):
        require_staff_mfa(staff, _claims(row, method="passkey"))
    require_staff_mfa(staff, _claims(row, method="totp"))
    UserMFA.objects.filter(pk=row.pk).update(enabled_at=None)
    assert not mfa_policy.staff_factor_enrolled(staff)
