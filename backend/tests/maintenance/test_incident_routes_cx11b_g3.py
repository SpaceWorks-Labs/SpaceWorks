"""Incident rows: decision 520 object standing, 481/494 space concealment."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from apps.maintenance.incidents.models import Incident, IncidentAction
from tests.maintenance.l16_helpers import world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, person_client, prove, send
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory]
STAFF = ["list", "create", "detail", "update", "action", "assignees", "done"]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", STAFF)
def test_incident_staff_route_effect_and_switch(operation, native):
    w = world("g3-incident")
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"safety.incidents"})
    w.space.save(update_fields=["enabled_features"])
    row = Incident.objects.create(makerspace=w.space, reporter=w.manager, title="Guard slipped", area="other")
    action = IncidentAction.objects.create(incident=row, description="Inspect guard")
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    routes = {
        "list": ("admin-incidents", [w.space.pk], "get", {}, 200, None),
        "create": ("admin-incidents", [w.space.pk], "post", {"title": "Floor wet"}, 201, "incident.reported"),
        "detail": ("admin-incident-detail", [row.pk], "get", {}, 200, None),
        "update": ("admin-incident-detail", [row.pk], "patch", {"status": "triaged"}, 200,
                   "incident.status_changed"),
        "action": ("admin-incident-actions", [row.pk], "post", {"description": "Replace guard"}, 201,
                   "incident.action_added"),
        "assignees": ("admin-incident-assignees", [row.pk], "get", {}, 200, None),
        "done": ("admin-incident-action-detail", [action.pk], "patch", {"done": True}, 200, "incident.action_done"),
    }
    name, args, method, body, status, audit = routes[operation]

    def check(response):
        row.refresh_from_db()
        if operation in {"list", "detail"}:
            records = response.data["results"] if operation == "list" else [response.data]
            assert [(r["id"], r["title"]) for r in records] == [(row.pk, "Guard slipped")]
        elif operation == "assignees":
            assert response.data == {"results": [{"id": w.manager.pk, "display_name":
                w.manager.display_name or w.manager.get_full_name() or w.manager.username}]}
        elif operation == "create":
            created = Incident.objects.get(pk=response.data["id"])
            assert (created.title, created.reporter_id, created.status) == ("Floor wet", w.manager.pk, "reported")
            assert Incident.objects.filter(makerspace=w.space).count() == 2
        elif operation == "update":
            assert (row.status, row.triaged_by_id) == ("triaged", w.manager.pk)
        elif operation == "action":
            assert list(row.actions.order_by("pk").values_list("description", flat=True)) == [
                "Inspect guard", "Replace guard"]
        else:
            action.refresh_from_db()
            assert action.done_at is not None and action.done_by_id == w.manager.pk

    prove(w.space, {"incident": row, "action": action}, "safety.incidents",
          lambda c: send(c or client, name, args, method, body), check, status=status,
          off=(404, "feature_disabled"), outsiders=[(outsider, foreign_refusal(native, space_path=operation in {"list", "create"}))],
          audits={audit: 1} if audit else {})


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("method", ["get", "post"])
def test_member_incident_own_report_and_switch(method, native):
    # Member register is a personal collection, not the staff makerspace gate
    # (494). A second member sees only their own rows; cannot read our reporter.
    from tests.return_helpers import make_member
    from tests.modules.switch_matrix_object_helpers import response_pair
    from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
    w = world("g3-member-incident")
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"safety.incidents"})
    w.space.save(update_fields=["enabled_features"])
    person = make_member("g3-reporter", w.space, membership_role="member", role="requester")
    other = make_member("g3-second", w.space, membership_role="member", role="requester")
    row = Incident.objects.create(makerspace=w.space, reporter=person, title="My report")
    client, second = (person_client(p, w.space, native) for p in (person, other))
    foreign = foreign_client(native, personal=True)
    body = {"title": "New report"}

    def check(response):
        if method == "get":
            assert [(r["id"], r["title"]) for r in response.data["results"]] == [(row.pk, "My report")]
        else:
            created = Incident.objects.get(pk=response.data["id"])
            assert (created.reporter_id, created.title) == (person.pk, "New report")
            assert Incident.objects.filter(reporter=person).count() == 2

    url_args = [w.space.pk]
    for caller in (second, foreign):
        with no_domain_writes():
            answer = send(caller, "member-incidents", url_args)
        assert answer.status_code == 200 and answer.data["results"] == []
    # No-standing POST is the decided member 403, and gate-first while off.
    with no_domain_writes():
        answer = send(foreign, "member-incidents", url_args, "post", body)
    assert response_pair(answer) == (403, "permission_denied")
    original = switch(w.space, "safety.incidents")
    for caller in (second, foreign):
        with no_domain_writes():
            answer = send(caller, "member-incidents", url_args, method, body)
        assert response_pair(answer) == (404, "feature_disabled")
    switch(w.space, "safety.incidents", original=original)
    prove(w.space, {"incident": row}, "safety.incidents",
          lambda c: send(c or client, "member-incidents", url_args, method, body), check,
          status=200 if method == "get" else 201, off=(404, "feature_disabled"),
          audits={} if method == "get" else {"incident.reported": 1})
    with no_domain_writes():
        answer = send(foreign, "member-incidents", url_args, "post", body)
    assert response_pair(answer) == (403, "permission_denied")

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
