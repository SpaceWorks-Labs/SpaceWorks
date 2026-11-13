from tests.accounts.account_factories import make_staff
from types import SimpleNamespace
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from apps.accounts import reauthentication as service
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from tests.accounts.test_reauthentication import request, PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def platform_origin(settings):
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]


@pytest.fixture
def staff():
    space = Makerspace.objects.create(name="Sensitive tenant", slug="sensitive-tenant")
    user = make_staff(space, username="sensitive-manager", password=PASSWORD)
    return user, space


@pytest.mark.parametrize("path,method", [
    ("/api/v1/admin/makerspaces/{id}/roles", "post"),
    ("/api/v1/admin/makerspaces/{id}/memberships/1/role", "patch"),
    ("/api/v1/admin/makerspace/{id}/api-clients", "post"),
    ("/api/v1/admin/api-clients/1/rotate-secret", "post"),
    ("/api/v1/admin/events/1/staff-invites/", "post"),
    ("/api/v1/admin/event-staff-grants/1/revoke/", "post"),
    ("/api/v1/admin/spaces/1/staff-invites/", "post"),
    ("/api/v1/admin/booking-staff-grants/1/revoke/", "post"),
])
def test_every_sensitive_mutation_requires_recent_proof_before_mutation(staff, path, method):
    user, space = staff
    req = request(user)
    client = APIClient(); client.force_authenticate(user, token=req.auth)
    result = getattr(client, method)(path.format(id=space.pk), {}, format="json")
    assert result.status_code == 403
    assert result.data["code"] == "recent_reauth_required"


def test_recent_proof_never_expands_cross_tenant_role_authority(staff):
    user, local = staff
    foreign = Makerspace.objects.create(name="Foreign", slug="foreign-sensitive")
    req = request(user)
    service.verify(req, password=PASSWORD)
    client = APIClient(); client.force_authenticate(user, token=req.auth)
    # Fixed roles: no role can be created; the sensitive write is a role-set change.
    from apps.makerspaces.models import MakerspaceRole
    target = User.objects.create_user(username="foreign-target", password="Target-pass-123!")
    member = MakerspaceRole.objects.get(makerspace=foreign, slug="member")
    manager = MakerspaceRole.objects.get(makerspace=foreign, slug="event_manager")
    membership = MakerspaceMembership.objects.create(
        makerspace=foreign, user=target, role="custom", assigned_role=member,
    )
    response = client.patch(
        f"/api/v1/admin/makerspaces/{foreign.pk}/memberships/{membership.pk}/role",
        {"role_ids": [manager.pk]}, format="json",
    )
    assert response.status_code == 404
    membership.refresh_from_db()
    assert membership.assigned_role_id == member.pk


def test_control_and_staff_proofs_are_separate(staff, monkeypatch):
    user = User.objects.create_superuser(username="separate-proof-root", password=PASSWORD)
    req = request(user)
    service.verify(req, password=PASSWORD)
    control = APIRequestFactory().post("/control/apiclients/apiclient/")
    control.user = user
    control.session = SimpleNamespace(session_key="other-control-session")
    monkeypatch.setattr("apps.accounts.control_mfa.session_verified", lambda request: True)
    result = RecentReauthenticationAdminMixin()._recent_redirect(control)
    assert result.status_code == 302 and result.url.startswith("/mfa/reauth/")
    assert service.require_recent_reauth(req)


def test_control_model_and_inline_paths_cannot_bypass_recent_proof():
    from apps.accounts.reauthentication_control import sensitive_control_request
    from apps.makerspaces.models import Makerspace
    from apps.accounts.models import User
    callback = SimpleNamespace(model_admin=SimpleNamespace(model=User))
    req = APIRequestFactory().post("/control/accounts/user/1/change/", {})
    assert sensitive_control_request(req, callback)
    callback.model_admin.model = Makerspace
    req = APIRequestFactory().post("/control/makerspaces/makerspace/1/change/", {"memberships-0-role": "space_manager"})
    assert sensitive_control_request(req, callback)
    req = APIRequestFactory().post("/control/makerspaces/makerspace/1/change/", {"name": "Rename"})
    assert not sensitive_control_request(req, callback)
