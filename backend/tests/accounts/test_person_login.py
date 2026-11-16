"""U-A2: one password door; every person gets a person token; the superadmin stays separate."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksAccessToken
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import grant_staff_role, make_membership, make_staff

pytestmark = pytest.mark.django_db
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
PASSWORD = "Strong-Person-Pass-91"
PLATFORM_ORIGIN = "http://localhost:5000"
OTHER_ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture
def space():
    return Makerspace.objects.create(name="Person Space", slug="person-space")


def login(username, *, origin=PLATFORM_ORIGIN, **extra):
    client = APIClient()
    client.credentials(HTTP_ORIGIN=origin)
    return client, client.post(LOGIN, {"username": username, "password": PASSWORD, **extra}, format="json")


def claims(response):
    return SpaceWorksAccessToken(response.data["access"])


def test_member_login_issues_person_token_without_makerspace_claim(space):
    person = User.objects.create_user("plain-person", email="plain@person.test", password=PASSWORD)
    make_membership(person, space)
    _client, response = login("plain-person")
    assert response.status_code == 200, response.data
    token = claims(response)
    assert token["kind"] == "person" and token["surface"] == "member"
    assert "makerspace" not in token.payload and "staff_scope" not in token.payload
    user = response.data["user"]
    assert user["kind"] == "person" and "account_kind" not in user  # alias removed by U-B (#162(4))
    assert user["has_staff_role"] is False and user["staff_roles"] == []
    assert user["is_platform"] is False and user["mfa_grace_ends_at"] is None
    assert [entry["tracks"] for entry in user["makerspaces"]] == [["community"]]


def test_converted_staff_signs_in_with_username_and_sees_staff_roles(space):
    staff = make_staff(space, username="converted-sm", password=PASSWORD, email="")
    _client, response = login("converted-sm", context="staff", makerspace=space.slug)
    assert response.status_code == 200, response.data
    assert claims(response)["kind"] == "person"
    user = response.data["user"]
    assert user["has_staff_role"] is True and user["has_elevated_authority"] is True
    [entry] = user["staff_roles"]
    assert entry["makerspace"] == {"id": space.pk, "slug": space.slug, "name": space.name}
    assert [role["slug"] for role in entry["roles"]] == ["space_manager"]
    assert "manage_makerspace" in entry["actions"]
    [space_entry] = user["makerspaces"]
    assert space_entry["tracks"] == ["staff"] and space_entry["role_slug"] == "space_manager"
    assert "manage_makerspace" in space_entry["actions"]


def test_held_email_cannot_sign_in_but_username_can(space):
    # A converted account whose colliding email was put on hold has a blank email.
    make_staff(space, username="held-email", password=PASSWORD, email="")
    _client, by_email = login("held@person.test")
    assert by_email.status_code == 401
    _client, by_name = login("held-email")
    assert by_name.status_code == 200


def test_person_with_both_tracks_gets_one_merged_entry(space):
    person = User.objects.create_user("both-tracks", email="both@person.test", password=PASSWORD)
    make_membership(person, space, can_refer=True)
    grant_staff_role(person, space, role_slug="inventory_manager")
    _client, response = login("both@person.test")
    assert response.status_code == 200, response.data
    [entry] = response.data["user"]["makerspaces"]
    assert entry["tracks"] == ["community", "staff"] and entry["role_slug"] == "inventory_manager"
    assert entry["can_refer"] is True and "view_inventory" in entry["actions"]


def test_platform_account_only_from_platform_origin_and_by_username():
    root = User.objects.create_superuser("platform-root", email="root@platform.test", password=PASSWORD)
    assert root.account_kind == "platform"
    _client, foreign = login("platform-root", origin=OTHER_ORIGIN)
    assert foreign.status_code == 401
    _client, response = login("platform-root")
    assert response.status_code == 200, response.data
    assert claims(response)["kind"] == "platform" and response.data["surface"] == "platform"
    assert response.data["user"]["is_platform"] is True and response.data["user"]["kind"] == "platform"


def test_person_email_wins_over_platform_email():
    User.objects.create_superuser("shared-root", email="shared@person.test", password="Other-Root-Pass-77")
    person = User.objects.create_user("shared-person", email="shared@person.test", password=PASSWORD)
    _client, response = login("shared@person.test")
    assert response.status_code == 200
    assert response.data["user"]["id"] == person.pk


def test_member_password_switch_never_locks_out_staff(space, monkeypatch):
    monkeypatch.setattr("apps.accounts.login_methods.password_login_enabled", lambda: False)
    User.objects.create_user("switch-member", email="switch@person.test", password=PASSWORD)
    make_staff(space, username="switch-staff", password=PASSWORD)
    _client, member = login("switch-member")
    assert member.status_code == 403
    _client, unknown = login("nobody-at-all")
    assert unknown.status_code == 403
    _client, staff = login("switch-staff")
    assert staff.status_code == 200, staff.data


def test_me_reports_staff_roles_for_a_bearer_session(space):
    from tests.stage4.helpers import bearer_client
    staff = make_staff(space, username="me-staff")
    response = bearer_client(staff).get(ME)
    assert response.status_code == 200, response.data
    assert response.data["session_authority"] == "member"
    assert [entry["makerspace"]["id"] for entry in response.data["staff_roles"]] == [space.pk]
