"""Both service-report surfaces must expose the retained completed job and machine hours."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.machines.models import MachineServiceRequest, ServiceQueue
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider
from tests.return_helpers import make_user

pytestmark = [pytest.mark.django_db, pytest.mark.area_machine_service, pytest.mark.area_reports]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["reports", "machine_service"])
def test_tenant_service_report_requires_sources_and_restores_completed_job(native, key):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    machine = objects["machine"]
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=machine.machine_type, name="Retained queue")
    job = MachineServiceRequest.objects.create(makerspace=space, queue=queue, requester=actor, member=actor,
        assigned_machine=machine, title="Retained job", status="completed", actual_minutes=90, completed_at=timezone.now())
    url = reverse("admin-makerspace-machine-service-report", kwargs={"makerspace_id": space.pk})
    def check(response):
        assert len(response.data["status_totals"]) == 1
        assert (response.data["status_totals"][0]["submitted"], response.data["status_totals"][0]["completed"]) == (1, 1)
        row = response.data["machines"][0]
        assert (row["machine_id"], row["request_count"], row["completed_count"], row["completed_hours"]) == (machine.pk, 1, 1, 1.5)
        job.refresh_from_db()
        assert (job.status, job.actual_minutes, job.assigned_machine_id) == ("completed", 90, machine.pk)
    foreign = outsider(native)
    cycle(space, key, lambda: client.get(url), check, foreign=lambda: foreign.get(url), foreign_native=native)


@pytest.mark.parametrize("key", ["reports", "machine_service"])
def test_global_service_report_omits_disabled_tenant_and_restores_same_job(key):
    space, _client, objects = object_world(False)
    actor = User.objects.get(username="sx-real-object-manager")
    root = make_user("g4-global-service-root", role=User.Role.SUPERADMIN, access_status="active")
    client = client_for(root, space, False)
    machine = objects["machine"]
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=machine.machine_type, name="Retained queue")
    MachineServiceRequest.objects.create(makerspace=space, queue=queue, requester=actor, member=actor,
        assigned_machine=machine, title="Retained job", status="completed", actual_minutes=90, completed_at=timezone.now())
    url = reverse("admin-machine-service-report")
    foreign = outsider(False)
    def check(response):
        assert [(r["makerspace_id"], r["completed"]) for r in response.data["status_totals"]] == [(space.pk, 1)]
        assert [(r["machine_id"], r["completed_hours"]) for r in response.data["machines"]] == [(machine.pk, 1.5)]
    def empty(response):
        assert response.data == {"status_totals": [], "machines": [], "consumption": [], "failure_summary": []}
    # Global aggregate stays available and filters tenant sources. Platform device
    # authority is forbidden; a local staff caller retains the explicit 403 (494).
    cycle(space, key, lambda: client.get(url), check, off=(200, None), off_check=empty,
          foreign=lambda: foreign.get(url), foreign_pair=(403, "permission_denied"))
