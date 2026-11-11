"""Decision 244: HTTP condition matrix for the safety incident register (switch, roles, validation, isolation)."""
import pytest
from rest_framework.test import APIClient

from apps.maintenance.incidents.models import Incident
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _member, _space

pytestmark = pytest.mark.django_db


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _space_with_incidents(slug, feature=True):
    space = _space(slug, modules=("machines",), certifications=False)
    if feature:
        space.enabled_features = sorted(set(space.enabled_features or []) | {"safety.incidents"})
        space.save(update_fields=["enabled_features"])
    return space


def test_every_incident_route_is_404_while_the_feature_is_off():
    space = _space_with_incidents("incc-off", feature=False)
    boss = staff_account(space, "incc-off-boss", "space_manager")
    member, _ = _member(space, "incc-off-member")
    assert _client(boss).get(f"/api/v1/admin/makerspaces/{space.pk}/incidents").status_code == 404
    assert _client(boss).post(f"/api/v1/admin/makerspaces/{space.pk}/incidents", {"title": "x"},
                              format="json").status_code == 404
    assert _client(member).post(f"/api/v1/member/makerspaces/{space.pk}/incidents", {"title": "x"},
                                format="json").status_code == 404
    assert not Incident.objects.filter(makerspace=space).exists()


@pytest.mark.parametrize("slug,allowed", [("space_manager", True), ("member", False), ("handover", False)])
def test_staff_register_access_by_role(slug, allowed):
    space = _space_with_incidents(f"incc-role-{slug}".replace("_", "-"))
    actor = staff_account(space, f"incc-actor-{slug}", slug)
    response = _client(actor).get(f"/api/v1/admin/makerspaces/{space.pk}/incidents")
    assert (response.status_code == 200) is allowed
    if not allowed:
        assert response.status_code in (403, 404)


def test_anonymous_is_refused_on_staff_and_member_routes():
    space = _space_with_incidents("incc-anon")
    assert _client().get(f"/api/v1/admin/makerspaces/{space.pk}/incidents").status_code in (401, 403)
    assert _client().post(f"/api/v1/member/makerspaces/{space.pk}/incidents", {"title": "x"},
                          format="json").status_code in (401, 403)


def test_member_report_validation_and_bad_links_are_rejected():
    space = _space_with_incidents("incc-valid")
    member, _ = _member(space, "incc-valid-member")
    url = f"/api/v1/member/makerspaces/{space.pk}/incidents"
    client = _client(member)
    assert client.post(url, {}, format="json").status_code == 400
    assert client.post(url, {"title": "x", "severity": "catastrophic"}, format="json").status_code == 400
    assert client.post(url, {"title": "x", "kind": "gossip"}, format="json").status_code == 400
    assert client.post(url, {"title": "y" * 201}, format="json").status_code == 400
    assert not Incident.objects.filter(makerspace=space).exists()


def test_another_spaces_machine_cannot_be_linked_and_foreign_incident_is_404():
    from apps.machines.models import Machine
    from tests.machines.certification_helpers import _machine_type
    mine, theirs = _space_with_incidents("incc-iso-a"), _space_with_incidents("incc-iso-b")
    foreign_machine = Machine.objects.create(makerspace=theirs, machine_type=_machine_type(theirs), name="Foreign")
    my_boss = staff_account(mine, "incc-iso-a-boss", "space_manager")
    their_boss = staff_account(theirs, "incc-iso-b-boss", "space_manager")
    url = f"/api/v1/admin/makerspaces/{mine.pk}/incidents"
    assert _client(my_boss).post(url, {"title": "x", "machine_id": foreign_machine.pk},
                                 format="json").status_code == 404
    created = _client(their_boss).post(f"/api/v1/admin/makerspaces/{theirs.pk}/incidents", {"title": "theirs"},
                                       format="json")
    assert created.status_code == 201
    incident_id = created.json()["id"]
    assert _client(my_boss).get(f"/api/v1/admin/incidents/{incident_id}").status_code == 404
    assert _client(my_boss).patch(f"/api/v1/admin/incidents/{incident_id}", {"status": "triaged"},
                                  format="json").status_code == 404
    assert Incident.objects.get(pk=incident_id).status == Incident.Status.REPORTED


def test_action_assignee_must_be_an_active_member_of_the_space():
    space = _space_with_incidents("incc-assignee")
    boss = staff_account(space, "incc-assignee-boss", "space_manager")
    outsider, _ = _member(_space_with_incidents("incc-assignee-other"), "incc-outsider")
    client = _client(boss)
    incident_id = client.post(f"/api/v1/admin/makerspaces/{space.pk}/incidents", {"title": "Cut"},
                              format="json").json()["id"]
    url = f"/api/v1/admin/incidents/{incident_id}/actions"
    refused = client.post(url, {"description": "Fix", "assignee_id": outsider.pk}, format="json")
    missing = client.post(url, {"description": "Fix", "assignee_id": 99999999}, format="json")
    assert refused.status_code == missing.status_code == 400 and refused.json() == missing.json()
    assert client.post(url, {}, format="json").status_code == 400
