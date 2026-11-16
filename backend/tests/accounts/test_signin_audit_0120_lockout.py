"""REDIS-AUTH-AUDIT (decision 339b): the login-method switches count every way in.

Before 0.12.0 the complete-state check counted only a password and linked providers, so
switching phone sign-in or passkeys off could strand a member who signs in only that way,
and switching social off was refused for a member who also had a phone or a passkey.
"""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.login_methods_validation import validate_login_methods
from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db
NUMBER = "+14155552671"


@pytest.fixture
def google():
    row = PlatformSocialAuthSettings.load()
    row.google_web_client_id = "google-client"
    row.save()
    return row


@pytest.fixture
def sms(monkeypatch):
    monkeypatch.setattr("apps.integrations.sms.sms_configured", lambda: True)


def member(name, *, providers=(), phone=False, passkeys=0, password=None):
    user = User.objects.create_user(username=name, email=f"{name}@example.test", password=password)
    for provider in providers:
        SocialIdentity.objects.create(user=user, provider=provider, provider_sub=f"{name}-{provider}")
    if phone:
        User.objects.filter(pk=user.pk).update(phone_e164=NUMBER, phone_verified_at=timezone.now())
    for index in range(passkeys):
        WebAuthnCredential.objects.create(user=user, credential_id=f"{name}-cred-{index}", public_key=b"key",
                                          rp_id="localhost")
    return user


def test_phone_only_member_blocks_switching_phone_sign_in_off(sms):
    member("phone-only", phone=True)
    with pytest.raises(ValidationError, match="lock out"):
        validate_login_methods(PlatformLoginMethods(phone_enabled=False), current=PlatformLoginMethods())


def test_phone_switch_is_free_when_sms_was_never_configured():
    # Without an SMS provider the phone was never a way in, so turning it off strands nobody new.
    member("phone-unconfigured", phone=True)
    validate_login_methods(PlatformLoginMethods(phone_enabled=False), current=PlatformLoginMethods())


def test_a_verified_phone_rescues_switching_social_off(google, sms):
    member("google-and-phone", providers=["google"], phone=True)
    validate_login_methods(PlatformLoginMethods(social_enabled=False), current=PlatformLoginMethods())


def test_social_off_still_refused_without_another_way_in(google, sms):
    member("google-only", providers=["google"])
    with pytest.raises(ValidationError, match="lock out"):
        validate_login_methods(PlatformLoginMethods(social_enabled=False), current=PlatformLoginMethods())


def test_a_passkey_rescues_social_and_passkey_only_blocks_passkeys_off(google):
    member("google-and-passkey", providers=["google"], passkeys=1)
    validate_login_methods(PlatformLoginMethods(social_enabled=False), current=PlatformLoginMethods())
    member("passkey-only", passkeys=1)
    with pytest.raises(ValidationError, match="lock out"):
        validate_login_methods(PlatformLoginMethods(passkeys_enabled=False), current=PlatformLoginMethods())


def test_staff_password_survives_the_member_password_switch(google):
    space = Makerspace.objects.create(name="Audit lab", slug="audit-lab")
    staff = make_staff(space, username="audit-staff", password="Staff password 77!")
    SocialIdentity.objects.create(user=staff, provider="google", provider_sub="staff-google")
    validate_login_methods(PlatformLoginMethods(password_enabled=False, social_enabled=False),
                           current=PlatformLoginMethods())


def test_password_only_members_are_governed_by_the_password_switch_alone():
    # Documented operator choice: member password sign-in may be switched off (staff keep theirs).
    member("password-only", password="Member password 77!")
    validate_login_methods(PlatformLoginMethods(password_enabled=False), current=PlatformLoginMethods())
