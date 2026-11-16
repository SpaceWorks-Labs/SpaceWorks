"""Lane S0 (accounts 0051): a staff device grant accepts a passkey as its enabled factor."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import PlatformLoginMethods, User, WebAuthnCredential
from apps.accounts.models_mfa import UserMFA
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import device_grant, grant_staff_role

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff():
    space = Makerspace.objects.create(name="Passkey space", slug="passkey-space")
    person = User.objects.create_user("passkey-staff", email="pk@example.test", password="x" * 20)
    grant_staff_role(person, space)
    return person, space


def staff_grant(person, space):
    """A staff grant WITHOUT the factory's automatic authenticator, so the factor is explicit."""
    from apps.accounts.models import DeviceGrant

    registration = device_grant(person).registration  # an approved member grant supplies the registration
    now = timezone.now()
    return DeviceGrant.objects.create(
        registration=registration, user=person, platform=registration.platform, app_id=registration.app_id,
        environment=registration.environment, credential_generation=person.credential_generation,
        signing_identity=f"TEAM.{registration.app_id}", attestation_subject_fingerprint="f" * 64,
        attested_at=now, last_used_at=now, authority="staff", staff_makerspace_id=space.pk,
        login_method="password",
    )


def add_passkey(person):
    WebAuthnCredential.objects.create(user=person, credential_id="cred-1", public_key=b"k", rp_id="space.test")


def test_refused_without_any_factor(staff):
    with pytest.raises(IntegrityError, match="a factor and attestation"), transaction.atomic():
        staff_grant(*staff)


def test_accepted_with_a_passkey_only(staff):
    person, space = staff
    add_passkey(person)
    assert not UserMFA.objects.filter(user=person).exists()
    assert staff_grant(person, space).authority == "staff"


def test_accepted_with_an_authenticator_only(staff):
    person, space = staff
    UserMFA.objects.create(user=person, enabled_at=timezone.now())
    assert staff_grant(person, space).authority == "staff"


def test_passkey_does_not_count_while_platform_passkeys_are_off(staff):
    person, space = staff
    add_passkey(person)
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"passkeys_enabled": False})
    with pytest.raises(IntegrityError, match="a factor and attestation"), transaction.atomic():
        staff_grant(person, space)


def test_member_grants_need_no_factor(staff):
    person, _space = staff
    assert device_grant(person).authority == "member"
