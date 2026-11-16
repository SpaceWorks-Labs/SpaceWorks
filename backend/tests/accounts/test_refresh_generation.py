"""U-A2: device refresh honours the deployment auth generation and the minimum app version."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant, User
from apps.accounts.native_app_version import NativeAppUpdateRequired, assert_supported, parse
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.backup.models import DeploymentRecoveryState
from tests.accounts.account_factories import device_grant

pytestmark = pytest.mark.django_db
REFRESH = "/api/v1/auth/device/refresh"


def pair(username="gen-person"):
    person = User.objects.create_user(username, password="x" * 20)
    grant = device_grant(person)
    _access, refresh, _family = issue_device_token_pair(person, grant)
    return person, grant, refresh


def bump_generation():
    import uuid
    state = DeploymentRecoveryState.load()
    DeploymentRecoveryState.objects.filter(pk=state.pk).update(auth_generation=uuid.uuid4())


def test_stale_generation_revokes_the_family_with_session_revoked():
    _person, grant, refresh = pair()
    bump_generation()
    response = APIClient().post(REFRESH, {"refresh": refresh}, format="json")
    assert response.status_code == 401
    assert response.data["code"] == "session_revoked"
    grant.refresh_from_db()
    assert grant.status == DeviceGrant.Status.REVOKED


def test_current_generation_still_rotates():
    _person, _grant, refresh = pair("gen-current")
    response = APIClient().post(REFRESH, {"refresh": refresh}, format="json")
    assert response.status_code == 200, response.data


def test_minimum_app_version_refuses_old_and_unversioned_apps(settings):
    settings.MIN_NATIVE_APP_VERSION_ANDROID = "2.1.0"
    _person, grant, refresh = pair("gen-version")
    assert grant.platform == "android"
    for body in ({"refresh": refresh}, {"refresh": refresh, "app_version": "2.0.9"},
                 {"refresh": refresh, "app_version": "garbage"}):
        response = APIClient().post(REFRESH, body, format="json")
        assert response.status_code == 426, response.data
        assert response.data["code"] == "native_app_update_required"
        assert response.data["minimum_version"] == "2.1.0"
    # Nothing rotated: the same refresh works once the app is new enough.
    ok = APIClient().post(REFRESH, {"refresh": refresh, "app_version": "2.10.0"}, format="json")
    assert ok.status_code == 200, ok.data


def test_versions_compare_numerically_per_platform(settings):
    settings.MIN_NATIVE_APP_VERSION_IOS = "1.10.0"
    settings.MIN_NATIVE_APP_VERSION_ANDROID = ""
    assert parse("1.9.12") < parse("1.10.0")
    assert_supported("apple", "1.10.0")
    assert_supported("android", None)
    with pytest.raises(NativeAppUpdateRequired):
        assert_supported("apple", "1.9.99")


def test_device_login_checks_the_version_before_the_challenge(settings):
    settings.MIN_NATIVE_APP_VERSION_ANDROID = "3.0.0"
    response = APIClient().post("/api/v1/auth/device/login", {
        "platform": "android", "app_id": "org.spaceworks.app", "environment": "development",
        "username": "nobody", "password": "x", "challenge": "c", "attestation": {"a": "b"},
        "app_version": "2.9.9",
    }, format="json")
    assert response.status_code == 426
    assert response.data["code"] == "native_app_update_required"
