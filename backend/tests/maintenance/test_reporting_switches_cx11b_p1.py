"""Reporting switches preserve the original loan, booking or machine session."""
from datetime import timedelta

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking
from apps.machines.models import MachineSession, MachineServiceRequest, ServiceQueue
from tests.maintenance.l16_helpers import world
from tests.maintenance.route_support_cx11b_g3 import person_client
from tests.return_helpers import make_issued_request
from tests.inventory.switch_support_cx11b_p1 import prove_route

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("feature,key", [
    ("inventory.issue_reporting", "inventory.issue_reporting"), ("inventory.issue_reporting", "loans.enabled"),
    ("machines.issue_reporting", "machines.issue_reporting"), ("machines.issue_reporting", "machines"),
    ("bookings.issue_reporting", "bookings.issue_reporting"), ("bookings.issue_reporting", "bookings")])
def test_report_switch_is_inert_off_and_restores_the_same_used_subject(feature, key, native):
    w = world("p1-report")
    now = timezone.now()
    if feature.startswith("inventory"):
        origin = make_issued_request(w.space, w.manager, [(w.product, 1)])
        link = {"loan_id": origin.pk}
    elif feature.startswith("machines") and key == "machines":
        queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=w.machine.machine_type,
                                            name="Retained issue queue")
        origin = MachineServiceRequest.objects.create(queue=queue, makerspace=w.space, requester=w.manager, member=w.manager,
            assigned_machine=w.machine, title="Retained completed job", status="completed")
        link = {"machine_job_id": origin.pk}
    elif feature.startswith("machines"):
        # Sessions are the existing member reporting surface, independent of jobs.
        w.space.enabled_features = sorted(set(w.space.enabled_features) | {"machines.sessions"})
        w.space.save(update_fields=["enabled_features"])
        origin = MachineSession.objects.create(makerspace=w.space, machine=w.machine, machine_type=w.kind,
            member=w.manager, source="staff", started_at=now - timedelta(minutes=10))
        link = {"machine_session_id": origin.pk}
    else:
        origin = Booking.objects.create(space=w.room, member=w.manager, name="Retained booker",
            email=w.manager.email, starts_at=now, ends_at=now + timedelta(hours=1), status="confirmed")
        link = {"booking_id": origin.pk}
    body = {"makerspace_id": w.space.pk, "title": "Loose handle", "description": "Handle needs attention", **link}
    url = reverse("member-issues")
    # This is the account-wide owner endpoint: native member grants need no tenant
    # selector. The body still names the tenant and the service proves source ownership.
    person = origin.requester if "loan_id" in link else w.manager
    caller = person_client(person, w.space, native)
    prove_route(w.space, caller, {"origin": origin, "product": w.product}, key,
                lambda c: c.post(url, body, format="json"), off=(404, "capability_disabled"), on=(201, None))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
