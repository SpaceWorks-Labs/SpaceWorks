import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services_password_reset import GENERIC_CONFIRM_ERROR
from tests.accounts.password_reset_helpers import issue_otp
from tests.return_helpers import authenticated_client, make_member, make_space, make_user
from tests.accounts.reauth_helpers import force_recent_control_login as force_mfa_login

pytestmark = pytest.mark.django_db

CONFIRM_URL = reverse("auth-reset-password")
RECOVERED_PASSWORD = "Recovered-password-771!"


def confirm(user, code):
    return APIClient().post(
        CONFIRM_URL,
        {
            "email": user.email,
            "code": code,
            "new_password": RECOVERED_PASSWORD,
        },
        format="json",
    )


def assert_invalidated(user, code):
    response = confirm(user, code)
    assert response.status_code == 400
    assert response.json() == {"detail": GENERIC_CONFIRM_ERROR, "code": "invalid"}


def test_change_password_invalidates_an_issued_otp(monkeypatch):
    user = User.objects.create_user(
        username="invalidate-change",
        email="invalidate-change@example.org",
        password="Starting-password-419!",
        access_status=User.AccessStatus.ACTIVE,
    )
    code = issue_otp(user, monkeypatch)

    response = authenticated_client(user).post(
        reverse("auth-change-password"),
        {
            "current_password": "Starting-password-419!",
            "new_password": "Changed-password-552!",
        },
        format="json",
    )

    assert response.status_code == 200
    assert_invalidated(user, code)


def test_django_admin_reset_action_invalidates_an_issued_otp(monkeypatch):
    target = make_user(
        "invalidate-admin-target", access_status=User.AccessStatus.ACTIVE
    )
    code = issue_otp(target, monkeypatch)
    superadmin = make_user(
        "invalidate-admin-actor",
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
        is_staff=True,
        is_superuser=True,
    )
    client = Client()
    force_mfa_login(client, superadmin)

    response = client.post(
        reverse("admin:accounts_user_changelist"),
        {
            "action": "reset_password_selected",
            ACTION_CHECKBOX_NAME: [str(target.pk)],
            "index": "0",
            "control_confirmed": "yes",  # #188: the confirmed post
        },
        follow=True,
    )

    assert response.status_code == 200
    assert_invalidated(target, code)


@pytest.mark.skip(reason="U-A1/U-B: the staff-accounts set-password route is gone and a staff-track holder shares "
                  "their ONE account (and email) with their member self, so there is no 'separate member' to preserve")
def test_staff_reset_preserves_separate_members_issued_otp(monkeypatch):
    space = make_space("invalidate-staff-reset")
    actor = make_member("invalidate-staff-actor", space)
    member = User.objects.create_user("invalidate-separate-member", email="same-invalidation@example.test",
                                      password="Member original password 42!")
    code = issue_otp(member, monkeypatch)
    target = make_member("invalidate-staff-target", space,
        membership_role="inventory_manager", role=User.Role.REQUESTER)
    target.email = member.email
    target.save(update_fields=["email"])
    response = authenticated_client(actor).post(
        f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/{target.pk}/set-password/",
        {"generate": True}, format="json")
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.check_password(response.data["generated_password"])
    assert confirm(member, code).status_code == 200
    target.refresh_from_db()
    assert target.check_password(response.data["generated_password"])
