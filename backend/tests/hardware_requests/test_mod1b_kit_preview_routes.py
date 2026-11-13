"""MOD-1B: the staff kit-checklist preview route - input validation, tenancy, roles and the module switch.

The preview is read-only: every refusal here must leave requests, stock and audit untouched, and carry the exact
status (and typed code where the guard has one).
"""

import pytest

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from tests.account_split.p1_helpers import staff
from tests.return_helpers import (
    authenticated_client,
    make_accepted_request,
    make_issued_request,
    make_product,
    make_space,
)

pytestmark = pytest.mark.django_db


def manager_of(space, name, role="space_manager"):
    user, _ = staff(space, name, role=role)
    return authenticated_client(user), user


def url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/kit-checklist-preview"


@pytest.mark.parametrize("body, needle", [
    ({"phase": "return"}, "requires a request or loan reference"),
    ({"phase": "issue", "request_id": 1, "loan_id": 1}, "one request or loan reference"),
    ({"phase": "issue", "loan_id": 1}, "for return previews"),
])
def test_reference_rules_are_refused_with_400_before_anything_is_read(body, needle):
    space = make_space("mod1b-kit-refs")
    client, _ = manager_of(space, "mod1b-kit-refs-m")
    reply = client.post(url(space), body, format="json")
    assert reply.status_code == 400 and needle in str(reply.data), reply.data


@pytest.mark.parametrize("field, bad", [("phase", "sideways"), ("request_id", 0), ("request_id", "x"), ("container_id", 0)])
def test_malformed_fields_are_a_400_naming_the_field(field, bad):
    space = make_space("mod1b-kit-bad")
    client, _ = manager_of(space, "mod1b-kit-bad-m")
    reply = client.post(url(space), {"phase": "issue", "request_id": 1, field: bad}, format="json")
    assert reply.status_code == 400 and field in reply.data, reply.data


def test_duplicate_item_references_in_resolutions_are_a_400():
    space = make_space("mod1b-kit-dup")
    client, user = manager_of(space, "mod1b-kit-dup-m")
    request = make_issued_request(space, user, [(make_product(space), 1)])
    item = request.items.get()
    row = {"item_id": item.pk, "returned": 1, "damaged": 0, "missing": 0}
    reply = client.post(url(space), {"phase": "return", "request_id": request.pk, "resolutions": [row, row]}, format="json")
    assert reply.status_code == 400 and "resolutions" in reply.data and "unique" in str(reply.data)


def test_a_preview_of_an_own_request_is_a_200_and_changes_nothing():
    space = make_space("mod1b-kit-ok")
    client, user = manager_of(space, "mod1b-kit-ok-m")
    request = make_issued_request(space, user, [(make_product(space), 1)])
    audited = AuditLog.objects.count()
    reply = client.post(url(space), {"phase": "return", "request_id": request.pk}, format="json")
    assert reply.status_code == 200 and "components" in reply.data
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.ISSUED
    assert AuditLog.objects.count() == audited


def test_another_makerspaces_staff_and_request_are_404_and_nothing_leaks():
    space, other = make_space("mod1b-kit-t1"), make_space("mod1b-kit-t2")
    _client, user = manager_of(space, "mod1b-kit-t1-m")
    foreign = make_accepted_request(other, make_product(other), 1)
    outsider, _ = manager_of(other, "mod1b-kit-t2-m")
    mine = make_accepted_request(space, make_product(space, name="Mine"), 1)
    assert outsider.post(url(space), {"phase": "issue", "request_id": mine.pk}, format="json").status_code == 404
    own, _ = manager_of(space, "mod1b-kit-t1-m2")
    assert own.post(url(space), {"phase": "issue", "request_id": foreign.pk}, format="json").status_code == 404
    assert outsider.post(url(space), {"phase": "issue", "request_id": 987654}, format="json").status_code == 404


def test_a_role_without_handover_authority_is_refused_with_404():
    space = make_space("mod1b-kit-role")
    request = make_accepted_request(space, make_product(space), 1)
    events, _ = manager_of(space, "mod1b-kit-role-em", role="event_manager")
    assert events.post(url(space), {"phase": "issue", "request_id": request.pk}, format="json").status_code == 404


def test_a_direct_preview_needs_the_self_checkout_capability():
    space = make_space("mod1b-kit-cap")
    client, _ = manager_of(space, "mod1b-kit-cap-m")
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.self_checkout"]
    space.save(update_fields=["enabled_features"])
    reply = client.post(url(space), {"phase": "issue", "qr_payloads": ["abc"]}, format="json")
    assert reply.status_code == 404 and reply.data["code"] == "feature_disabled" and reply.data["feature"] == "inventory.self_checkout"
