"""Every loan queue read requires its seeded subject; foreign staff never see a gate."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("gate", ["surface", "loans.enabled"])
@pytest.mark.parametrize("name,status", [("hardware_requests:pending-requests", "pending_approval"), ("hardware_requests:accepted-requests", "accepted"),
    ("hardware_requests:active-loans", "issued"), ("hardware_requests:request-history", "returned"), ("hardware_requests:guest-admin-active-loans", "issued")])
def test_queue_returns_the_retained_request_on_both_transports(native, gate, name, status):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
                                         requester_name="Retained queue borrower", status=status)
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=1)
    url = reverse(name, kwargs={"makerspace_id": space.pk})
    foreign = outsider(native)
    surface = "guest_handover" if name.startswith("hardware_requests:guest-admin") else "request_workflow"

    def check(response):
        contains(response, row.pk)
        from tests.operations.route_support_cx11b_g4 import rows
        assert rows(response)[0]["status"] == status
        row.refresh_from_db()
        assert row.status == status
    # All these staff queues carry makerspace_id: decisions 481/494.
    cycle(space, surface if gate == "surface" else gate, lambda: send(client, "GET", url), check,
          foreign=lambda: send(foreign, "GET", url), foreign_native=native, refusal_key=surface)
