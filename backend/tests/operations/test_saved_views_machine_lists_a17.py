"""Open item A17: saved views on the Machines lists (machines, jobs, sessions, work orders, repairs)."""

from uuid import uuid4

import pytest

from apps.accounts import rbac
from apps.admin_api.staff_list_scope import ENTITY_ACTIONS, ENTITY_MODULES
from apps.makerspaces.models import MakerspaceMembership
from tests.machines.eta_helpers import world
from tests.machines.session_helpers import features
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db

MACHINE_ENTITIES = ("machines", "machine_jobs", "machine_sessions", "work_orders", "repairs")


def test_the_registry_names_each_machine_list_and_its_switches():
    for entity in MACHINE_ENTITIES:
        assert entity in ENTITY_ACTIONS and len(entity) <= 24
    assert ENTITY_MODULES["machine_jobs"] == "machine_service"
    assert ENTITY_MODULES["machine_sessions"] == ENTITY_MODULES["work_orders"] == "machines"
    # Handover-desk actions never open a machine list (224(d)); technicians reach repairs only.
    for entity in MACHINE_ENTITIES:
        assert rbac.Action.ISSUE_REQUEST not in ENTITY_ACTIONS[entity]
    assert rbac.Action.WORK_REPAIRS in ENTITY_ACTIONS["repairs"]
    assert rbac.Action.WORK_REPAIRS not in ENTITY_ACTIONS["machines"]


def _base(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/saved-views"


def test_a_space_manager_saves_and_lists_a_machine_jobs_view():
    w = world("a17-jobs")
    client = authenticated_client(w.staff)
    created = client.post(_base(w.space), {"entity": "machine_jobs", "name": "Laser backlog",
                                           "state": {"status": "active", "machine": "3"}}, format="json")
    assert created.status_code == 201, created.content
    listed = client.get(f"{_base(w.space)}?entity=machine_jobs")
    assert listed.status_code == 200 and [row["name"] for row in listed.json()["results"]] == ["Laser backlog"]


def test_session_and_work_order_views_follow_their_switches():
    w = world("a17-switch")
    client = authenticated_client(w.staff)
    features(w.space, remove={"machines.sessions", "machines.maintenance"})
    assert client.get(f"{_base(w.space)}?entity=machine_sessions").status_code == 404
    assert client.get(f"{_base(w.space)}?entity=work_orders").status_code == 404
    features(w.space, add={"machines.sessions"})
    assert client.get(f"{_base(w.space)}?entity=machine_sessions").status_code == 200


def test_an_area_manager_without_machine_authority_is_refused_machine_lists():
    w = world("a17-refuse")
    events = make_member(f"a17-ev-{uuid4().hex[:6]}", w.space, membership_role=MakerspaceMembership.Role.EVENT_MANAGER)
    client = authenticated_client(events)
    for entity in ("machines", "machine_jobs", "work_orders"):
        assert client.get(f"{_base(w.space)}?entity={entity}").status_code in (403, 404), entity
