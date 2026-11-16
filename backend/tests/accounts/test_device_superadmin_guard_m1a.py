"""Platform device grants are forbidden; kind changes cannot promote native authority."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import DeviceGrant, User
from apps.audit.models import AuditLog
from tests.accounts.account_factories import make_staff
from tests.accounts.native_helpers_m1d import attested_login, configure_apple
from tests.accounts.test_device_auth import REFRESH
from tests.accounts.test_phone_auth_p8 import NUMBER, sms_on
from tests.accounts.test_phone_device_login_m1a import confirm_device, start_device
from tests.accounts.test_social_first_grant import issue_challenge
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"


def test_platform_cannot_create_password_device_grant(settings, monkeypatch):
    # Stale since U-A2 5e5e9717 (#63): the native password door looks up persons only, so a
    # platform account reads exactly like an unknown username (401 invalid_credentials), not 403.
    user = User.objects.create_superuser(username="native-platform-password", password=PASSWORD)
    response, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert response.status_code == 401
    assert "access" not in response.data and "refresh" not in response.data
    assert not DeviceGrant.objects.filter(user=user).exists()
    assert AuditLog.objects.filter(action="auth.device_login_failed",
        meta__reason="invalid_credentials").exists()


# Stale since U-A2 fef4372c (#63): a staff member is a person whose phone sign-in is a member
# grant, so only the platform account is a "non-member phone identity" now.
@pytest.mark.parametrize("kind", ["platform"])
def test_nonmember_phone_identity_cannot_start_a_native_consumer_login(kind, settings, sms_on):
    configure_apple(settings)
    fields = {"phone_e164": NUMBER, "phone_verified_at": timezone.now()}
    if kind == "staff":
        user = make_staff(make_space("phone-staff-kind"), username="phone-staff-kind", **fields)
    else:
        user = User.objects.create_superuser(username="phone-platform-kind", **fields)
    raw = issue_challenge(APIClient())
    assert start_device(APIClient(), raw).status_code == 200
    assert sms_on == []
    assert confirm_device(APIClient(), raw, "123456").status_code == 400
    assert not DeviceGrant.objects.filter(user=user).exists()


def test_kind_cannot_change_after_device_issuance(settings, monkeypatch):
    user = User.objects.create_user(username="native-immutable-kind", password=PASSWORD)
    first, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert first.status_code == 200
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(account_kind="platform", is_superuser=True, role="superadmin")
    result = APIClient().post(REFRESH, {"refresh": first.data["refresh"]}, format="json")
    assert result.status_code == 200
    # Stale since U-A2 fef4372c: the token kind claim is "person" (or "platform"), never "member".
    assert AccessToken(result.data["access"])["kind"] == "person"
    assert DeviceGrant.objects.get(user=user).authority == "member"
