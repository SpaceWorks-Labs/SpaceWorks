"""Release 0.12.0 U2: who may be assigned an incident follow-up (decision 219 (e))."""
import pytest
from django.urls import reverse

from apps.accounts.rbac import Action
from apps.machines.models import Machine
from apps.maintenance.incidents import services
from tests.machines.certification_helpers import _machine_type, _manager, _member, _space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _incident_space(slug):
    space = _space(slug, modules=("machines",), certifications=False)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"safety.incidents"})
    space.save(update_fields=["enabled_features"])
    return space


def _ask(user, incident):
    response = authenticated_client(user).get(reverse("admin-incident-assignees", kwargs={"pk": incident.pk}))
    body = response.json() if response.status_code == 200 else {}
    return response.status_code, {row["id"] for row in body.get("results", [])}


def test_machine_incident_offers_space_manager_and_machine_manager_not_inventory_manager():
    space = _incident_space("asg")
    machine_type = _machine_type(space)
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Saw")
    head, _ = _manager(space, "asg-head", actions=(Action.MANAGE_MAKERSPACE,))
    machines_mgr, _ = _manager(space, "asg-mm", machine_type)
    stock_mgr, _ = _manager(space, "asg-stock", actions=(Action.EDIT_INVENTORY,))
    member, _ = _member(space, "asg-member")
    incident = services.report(member, space, title="Guard slipped", machine=machine)
    code, ids = _ask(head, incident)
    assert code == 200 and ids == {head.pk, machines_mgr.pk}
    assert _ask(stock_mgr, incident)[0] in (403, 404)  # cannot read the incident, so cannot list assignees


def test_other_area_incident_offers_only_space_managers():
    space = _incident_space("asg2")
    head, _ = _manager(space, "asg2-head", actions=(Action.MANAGE_MAKERSPACE,))
    _manager(space, "asg2-mm", _machine_type(space))
    member, _ = _member(space, "asg2-member")
    incident = services.report(member, space, title="Slippery floor")
    assert _ask(head, incident) == (200, {head.pk})
