"""Owner (member-surface) and staff (admin) cancel routes plus their registry entries."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.delegated_route_catalog import MEMBERSHIP_ROUTES
from apps.apiclients.scope_registry import SCOPE_REGISTRY, lookup, validate_registry
from apps.apiclients.scope_registry_routes import TARGET_TENANT_TOKEN
from apps.machines import role_scope
from apps.machines.models import MachineServiceRequest
from apps.machines.service_workflow import complete, start
from apps.machines.views_service_cancel import MemberMachineServiceCancelView
from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
from tests.machines.eta_helpers import approved, job, owner, world
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def owner_url(row):
    return f"/api/v1/member/machine-service/requests/by-token/{row.public_token}/owner"


def cancel_url(row):
    return f"/api/v1/member/machine-service/requests/{row.pk}/cancel"


def test_membership_off_owner_looks_up_and_cancels_their_own_job():
    w = world("owner-route")
    member = owner("owner-route")
    row = approved(w, 20, created=-5, member=member)
    lookup_response = as_user(member).get(owner_url(row))
    assert lookup_response.status_code == 200 and lookup_response["Cache-Control"] == "no-store"
    assert lookup_response.json() == {"request_id": row.pk, "can_cancel": True}
    response = as_user(member).post(cancel_url(row), {"reason": "No longer needed"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "cancelled" and response.json()["eta"] is None
    assert as_user(member).get(owner_url(row)).json()["can_cancel"] is False   # terminal now
    # An existing saved tracking link keeps working anonymously, and stays read-only.
    status = APIClient().get(f"/api/v1/public/machine-service/requests/{row.public_token}/status")
    assert status.status_code == 200 and status.json()["status"] == "cancelled"


def test_non_owner_anonymous_staff_and_platform_callers_are_refused():
    w = world("owner-refusals")
    row = job(w, member=owner("owner-refusals"))
    assert as_user(owner("owner-stranger")).get(owner_url(row)).status_code == 404
    assert as_user(owner("owner-stranger-2")).post(cancel_url(row), {}, format="json").status_code == 404
    assert APIClient().get(owner_url(row)).status_code == 401
    assert APIClient().post(cancel_url(row), {}, format="json").status_code == 401
    assert as_user(w.staff).post(cancel_url(row), {}, format="json").status_code == 403
    platform = make_user(f"owner-platform-{uuid4().hex[:6]}", is_superuser=True)
    assert as_user(platform).get(owner_url(row)).status_code == 403
    row.refresh_from_db()
    assert row.status == "pending"


def test_claim_sessions_are_refused_by_policy_and_by_the_view():
    for name, methods in (("member-machine-service-cancel", ("POST",)), ("member-machine-service-owner", ("GET", "HEAD"))):
        for method in methods:
            assert isinstance(policy_for(name, method), Refused)
    w = world("owner-claim")
    member = owner("owner-claim")
    row = job(w, member=member)
    request = APIRequestFactory().post(cancel_url(row), {}, format="json")
    force_authenticate(request, user=member)
    request.claim_session = SimpleNamespace(pk=1)  # DRF's Request proxies this attribute
    response = MemberMachineServiceCancelView.as_view()(request, pk=row.pk)
    assert response.status_code == 403
    assert MachineServiceRequest.objects.get(pk=row.pk).status == "pending"


def test_staff_cancel_route_uses_manage_scope_and_returns_null_eta():
    w = world("staff-cancel")
    row = approved(w, 20, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    response = authenticated_client(w.staff).post(f"/api/v1/admin/machine-service/requests/{row.pk}/cancel",
                                                  {"reason": "Machine fault"}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert (body["status"], body["eta"]) == ("cancelled", None) and body["cancelled_at"]
    foreign = world("staff-cancel-foreign")
    other = job(foreign)
    assert authenticated_client(w.staff).post(f"/api/v1/admin/machine-service/requests/{other.pk}/cancel",
                                              {}, format="json").status_code == 404
    done = approved(w, 5, created=-1)
    start(done, w.staff, role_scope.EXEMPT, machine_id=w.machines[1].pk)
    complete(done, w.staff, actual_minutes=5, consumptions=[])
    assert authenticated_client(w.staff).post(f"/api/v1/admin/machine-service/requests/{done.pk}/cancel",
                                              {}, format="json").status_code == 409


def test_route_registries_cover_every_new_route():
    stale, missing = validate_registry()
    assert not [key for key in stale + missing if "machine-service" in str(key)]
    for method in ("GET", "HEAD"):
        entry = SCOPE_REGISTRY[("public-machine-service-status", method)]
        assert entry.target_mode == TARGET_TENANT_TOKEN and entry.legacy_v1 is False
    assert lookup("member-machine-service-cancel", "POST") is None
    assert lookup("member-machine-service-owner", "GET") is None
    assert "admin-machine-service-request-cancel" in MEMBERSHIP_ROUTES
    w = world("owner-origin")
    row = job(w)
    request = SimpleNamespace(resolver_match=SimpleNamespace(url_name="member-machine-service-owner",
                                                             view_name="member-machine-service-owner",
                                                             kwargs={"public_token": row.public_token}),
                              method="GET", query_params={})
    targets, recognized = authoritative_route_resolution(request)
    assert recognized and targets == {w.space.pk}
