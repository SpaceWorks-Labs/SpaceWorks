"""REDIS-AUTH-AUDIT (decision 339b): removing a sign-in method never removes the last way in.

* unlinking a provider counts a verified phone and a passkey as ways in (it used to refuse a
  safe unlink because only a password counted);
* unlinking a phone used to be "always safe" -- it is not for a phone-only member;
* removing a passkey used to be refused only for staff -- a passkey-only member was stranded.
"""

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.models_social import SocialIdentity
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.audit.models import AuditLog
from tests.accounts.test_passkey_rp_id import origins, session  # noqa: F401 - autouse origins fixture
from tests.accounts.test_signin_audit_0120_lockout import NUMBER, google, member, sms  # noqa: F401
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_a_verified_phone_lets_a_member_unlink_their_last_provider(google, sms):
    user = member("unlink-phone-rescue", providers=["google"], phone=True)
    response = authenticated_client(user).delete("/api/v1/auth/social/providers/google")
    assert response.status_code == 204
    assert not SocialIdentity.objects.filter(user=user).exists()


def test_last_provider_is_still_protected_when_phone_sign_in_is_off(google, sms):
    from apps.accounts.models import PlatformLoginMethods

    PlatformLoginMethods.objects.create(pk=1, phone_enabled=False)
    user = member("unlink-phone-off", providers=["google"], phone=True)
    response = authenticated_client(user).delete("/api/v1/auth/social/providers/google")
    assert response.status_code == 409 and response.data["code"] == "last_credential"


def test_a_phone_only_member_cannot_unlink_their_phone(sms):
    user = member("phone-last", phone=True)
    response = authenticated_client(user).delete("/api/v1/auth/phone")
    assert response.status_code == 409 and response.data["code"] == "last_credential"
    user.refresh_from_db()
    assert user.phone_e164 == NUMBER and user.phone_verified_at is not None
    assert not AuditLog.objects.filter(action="member.phone_unlinked").exists()


def test_a_member_with_a_password_unlinks_their_phone(sms):
    user = member("phone-with-password", phone=True, password="Member password 77!")
    response = authenticated_client(user).delete("/api/v1/auth/phone")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.phone_e164 == "" and user.phone_verified_at is None
    assert AuditLog.objects.filter(action="member.phone_unlinked", actor=user).exists()


def test_a_passkey_only_member_cannot_remove_their_last_passkey():
    user = member("passkey-last", passkeys=1)
    row = WebAuthnCredential.objects.get(user=user)
    refused = session(user).delete(f"/api/v1/auth/passkeys/{row.pk}")
    assert refused.status_code == 403 and refused.data["code"] == "last_credential"
    assert WebAuthnCredential.objects.filter(pk=row.pk).exists()


def test_a_member_with_two_passkeys_removes_one():
    user = member("passkey-two", passkeys=2)
    row = WebAuthnCredential.objects.filter(user=user).first()
    removed = session(user).delete(f"/api/v1/auth/passkeys/{row.pk}")
    assert removed.status_code == 200, removed.data
    assert WebAuthnCredential.objects.filter(user=user).count() == 1
