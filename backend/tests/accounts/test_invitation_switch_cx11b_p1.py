"""A persisted invitation remains visible after the invitation switch returns."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services_staff_invitations import issue
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import object_world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_auth]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_staff_invitation_switch_retains_the_pending_invitation(native):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    row, _raw = issue(actor, space.pk, email="p1-invited@example.test", roles=["event_manager"])
    objects["invitation"] = row
    url = reverse("admin-staff-invitations", kwargs={"makerspace_id": space.pk})
    prove_route(space, client, objects, "staff.invitations", lambda c: c.get(url),
                check=lambda r: _contains(r, row.pk), outsiders=staff_outsiders(native))


def _contains(response, pk):
    assert pk in [row["id"] for row in response.data["results"]]

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
