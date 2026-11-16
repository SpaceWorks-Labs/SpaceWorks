"""Decision 242(f)(n): Technician work orders and incident reach; subject filters; extra search sources."""
import pytest
from django.urls import reverse

from apps.machines.models import Machine
from apps.maintenance.incidents.models import Incident
from apps.maintenance.models import TechnicianContact, WorkOrder
from apps.maintenance.views_work_orders import visible
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _machine_type
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def _world(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"machines", "maintenance", "staff_admin"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"machines.maintenance", "safety.incidents"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    kind = _machine_type(space)
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser 1")
    return space, kind, machine


def test_a_technician_sees_the_work_orders_assigned_to_them_and_no_others():
    space, kind, machine = _world("t242-wo")
    tech = staff_account(space, "t242-tech", "technician")
    other = staff_account(space, "t242-other", "technician")
    mine = WorkOrder.objects.create(makerspace=space, subject_type="machine", machine=machine, title="Mine",
                                    assignee=tech)
    WorkOrder.objects.create(makerspace=space, subject_type="machine", machine=machine, title="Theirs", assignee=other)
    assert list(visible(tech, space).values_list("pk", flat=True)) == [mine.pk]
    listed = authenticated_client(tech).get(reverse("admin-work-orders", args=[space.pk]))
    assert listed.status_code == 200 and [row["id"] for row in listed.json()] == [mine.pk]


def test_a_covering_technician_reads_machine_incidents_read_only():
    space, kind, machine = _world("t242-inc")
    tech = staff_account(space, "t242-inc-tech", "technician")
    contact = TechnicianContact.objects.create(makerspace=space, person=tech, kind=TechnicianContact.Kind.IN_HOUSE,
                                               name="Tech")
    contact.coverage.create(kind="machine_type", machine_type=kind)
    incident = Incident.objects.create(makerspace=space, title="Blade chipped", area="machines", machine=machine)
    client = authenticated_client(tech)
    listed = client.get(reverse("admin-incidents", args=[space.pk]))
    assert listed.status_code == 200 and [row["id"] for row in listed.json()["results"]] == [incident.pk]
    assert client.get(reverse("admin-incident-detail", args=[incident.pk])).status_code == 200
    assert client.patch(reverse("admin-incident-detail", args=[incident.pk]), {"status": "triaged"},
                        format="json").status_code == 404  # read, never triage
    filtered = client.get(reverse("admin-incidents", args=[space.pk]) + f"?machine={machine.pk + 999}")
    assert filtered.json()["results"] == []


def test_the_extra_search_sources_stay_behind_each_roles_own_action():
    from apps.admin_api.search_sources_more import extra_hits

    space, kind, machine = _world("t242-search")
    sm = staff_account(space, "t242-s-sm", "space_manager")
    member = staff_account(space, "t242-s-member", "member")
    Incident.objects.create(makerspace=space, title="Ladder fell", area="machines", machine=machine)
    assert any(hit["entity"] == "incidents" for hit in extra_hits(sm, space, "Ladder", 5))
    assert extra_hits(member, space, "Ladder", 5) == []
