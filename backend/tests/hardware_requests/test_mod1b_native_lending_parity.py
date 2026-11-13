"""MOD-1B: native (mobile) parity for the lending routes the phone apps call.

The native staff grant reaches the SAME views as the web console, behind `X-Makerspace-Id`. So every refusal and
every evidence rule must come out identically on both surfaces: same status, same typed code, same rows written.
A native member grant never reaches staff routes, and a restricted account is stopped at the door with a typed 401.
"""

from unittest.mock import Mock

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest, ReturnEvent
from tests.accounts.account_factories import make_staff
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.return_helpers import (
    authenticated_client,
    make_accepted_request,
    make_box,
    make_issue_evidence,
    make_issued_request,
    make_product,
    make_return_evidence,
    make_space,
    make_user,
    return_payload,
)

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class Surfaces:
    """The same staff person on the web console and on a native phone."""

    def __init__(self, user, home):
        self.user, self.home = user, home
        self.web = authenticated_client(user)
        self.native = None

    def post(self, surface, path, body, space=None):
        if surface == "web":
            return self.web.post(path, body, format="json")
        return self.native.post(path, body, format="json", HTTP_X_MAKERSPACE_ID=str((space or self.home).pk))


@pytest.fixture
def phone(settings, monkeypatch):
    home = make_space("mod1b-nat-home")
    user = make_staff(home, username="mod1b-nat-staff", role_slug="space_manager", password=PASSWORD,
                      email="mod1b-nat-staff@example.test")
    surfaces = Surfaces(user, home)
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    surfaces.native = bearer(login.data["access"])
    monkeypatch.setattr("apps.evidence.storage.object_exists", Mock(return_value=True))
    return surfaces


def outcome(response):
    return response.status_code, (response.data.get("code") if isinstance(response.data, dict) else None)


def accepted_with_box(space):
    request = make_accepted_request(space, make_product(space), 1)
    request.assigned_box = make_box(space)
    request.save(update_fields=["assigned_box", "updated_at"])
    return request


SURFACES = ["web", "native"]


@pytest.mark.parametrize("surface", SURFACES)
def test_issue_without_a_box_scan_is_the_same_400_on_both_surfaces(phone, surface):
    request = accepted_with_box(phone.home)
    evidence = make_issue_evidence(phone.home, phone.user)
    reply = phone.post(surface, f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "Out."})
    assert outcome(reply) == (400, "validation_error")
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED and request.issued_at is None


@pytest.mark.parametrize("surface", SURFACES)
def test_issue_of_a_pending_request_is_the_same_409_on_both_surfaces(phone, surface):
    request = make_accepted_request(phone.home, make_product(phone.home), 1)
    HardwareRequest.objects.filter(pk=request.pk).update(status=HardwareRequest.Status.PENDING_APPROVAL)
    evidence = make_issue_evidence(phone.home, phone.user)
    reply = phone.post(surface, f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "Out."})
    assert reply.status_code == 409, reply.data
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.PENDING_APPROVAL


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("remark", ["", "   "])
def test_return_with_a_blank_remark_is_the_same_400_and_records_nothing(phone, surface, remark):
    request = make_issued_request(phone.home, phone.user, [(make_product(phone.home), 1)])
    evidence = make_return_evidence(phone.home, phone.user)
    body = return_payload(request, evidence, remark=remark)
    reply = phone.post(surface, f"/api/v1/admin/requests/{request.pk}/return", body)
    assert reply.status_code == 400 and "remark" in str(reply.data)
    assert not ReturnEvent.objects.filter(request=request).exists()
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.ISSUED


def test_a_valid_return_writes_the_same_audit_trail_on_web_and_native(phone):
    counts = {}
    for surface in SURFACES:
        request = make_issued_request(phone.home, phone.user, [(make_product(phone.home, name=f"Tool {surface}"), 1)])
        evidence = make_return_evidence(phone.home, phone.user)
        reply = phone.post(surface, f"/api/v1/admin/requests/{request.pk}/return", return_payload(request, evidence))
        assert reply.status_code == 200, reply.data
        assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.RETURNED
        counts[surface] = sorted(AuditLog.objects.filter(target_id=str(request.pk)).values_list("action", flat=True))
    assert counts["web"] == counts["native"]
    assert counts["native"], "a return must be audited"


def test_native_staff_cannot_reach_another_makerspaces_request_and_nothing_changes(phone):
    other = make_space("mod1b-nat-other")
    foreign = accepted_with_box(other)
    evidence = make_issue_evidence(other, phone.user)
    audited = AuditLog.objects.filter(makerspace=other).count()
    for path in (f"/api/v1/admin/requests/{foreign.pk}/issue", f"/api/v1/admin/requests/{foreign.pk}/accept"):
        native = phone.post("native", path, {"evidence_id": evidence.pk, "remark": "x"})
        assert native.status_code == 403, native.data  # the origin gate: header space != the request's space
        web = phone.post("web", path, {"evidence_id": evidence.pk, "remark": "x"})
        assert web.status_code == 404, web.data  # the console: out of scope, no existence leak
    assert HardwareRequest.objects.get(pk=foreign.pk).status == HardwareRequest.Status.ACCEPTED
    assert AuditLog.objects.filter(makerspace=other).count() == audited


def test_a_native_member_grant_cannot_use_staff_lending_routes(settings, monkeypatch):
    home = make_space("mod1b-nat-member")
    member = make_user("mod1b-nat-member-u", access_status="active", password=PASSWORD)
    request = accepted_with_box(home)
    login, _ = attested_login(APIClient(), member, settings, monkeypatch)
    assert login.status_code == 200, login.data
    phone = bearer(login.data["access"])
    for path in (f"/api/v1/admin/requests/{request.pk}/issue", f"/api/v1/admin/requests/{request.pk}/return",
                 f"/api/v1/admin/makerspace/{home.pk}/direct-loans"):
        reply = phone.post(path, {}, format="json", HTTP_X_MAKERSPACE_ID=str(home.pk))
        assert reply.status_code == 403, (path, reply.data)
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.ACCEPTED


def test_a_restricted_account_is_stopped_at_the_door_for_loans_with_a_typed_401(settings, monkeypatch):
    home = make_space("mod1b-nat-restricted")
    member = make_user("mod1b-nat-restricted-u", access_status="active", password=PASSWORD)
    login, _ = attested_login(APIClient(), member, settings, monkeypatch)
    phone = bearer(login.data["access"])
    from apps.accounts.models import User
    User.objects.filter(pk=member.pk).update(access_status=User.AccessStatus.RESTRICTED)
    for path in (f"/api/v1/member/makerspaces/{home.pk}/loans/1/renew", f"/api/v1/member/makerspaces/{home.pk}/waitlist",
                 f"/api/v1/member/makerspaces/{home.pk}/borrowing-history"):
        reply = phone.get(path) if path.endswith(("waitlist", "history")) else phone.post(path, {}, format="json")
        assert reply.status_code == 401 and reply.data["code"] == "account_restricted", (path, reply.data)
