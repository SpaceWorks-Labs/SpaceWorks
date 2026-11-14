"""Direct loan and Station objects; contact-mode policy keeps returns available."""
from types import SimpleNamespace

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.hardware_requests.self_checkout_contact import contact_mode
from apps.makerspaces.models import Station
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, switch
from tests.return_helpers import make_member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.self_checkout", "loans.enabled"])
def test_self_checkout_switch_keeps_existing_direct_handout(native, key):
    space, _, _, product, loan, _, _ = setup_loan("p1-self-checkout")
    actor = make_member("p1-self-checkout-manager", space)
    path = reverse("hardware_requests:direct-loans", kwargs={"makerspace_id": space.pk})
    prove_route(space, client_for(actor, space, native), {"loan": loan, "product": product},
                key, lambda c: c.get(path), refusal_key="inventory.self_checkout")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.kiosk", "loans.enabled"])
def test_kiosk_switch_restores_the_same_station(native, key):
    space, client, _ = object_world(native)
    station = Station.objects.create(makerspace=space, kind="handover", name="Retained desk")
    path = reverse("admin-kiosk-station-detail", kwargs={"pk": station.pk})
    prove_route(space, client, {"station": station}, key, lambda c: c.get(path), refusal_key="inventory.kiosk")


@pytest.mark.parametrize("key", ["inventory.contact_self_checkout", "inventory.self_checkout", "loans.enabled"])
def test_contact_checkout_policy_off_refuses_taking_but_preserves_returns_and_restores(key):
    space, _, _ = object_world(False)
    # This parentless switch governs the account-less policy, irrespective of staff sign-in.
    switch(space, "member_accounts")
    request = SimpleNamespace(user=AnonymousUser())
    assert contact_mode(request, space, taking=True) is True
    original = switch(space, key)
    with connection.execute_wrapper(_no_write), pytest.raises(PermissionDenied) as error:
        contact_mode(request, space, taking=True)
    assert (error.value.status_code, error.value.get_codes()) == (403, "permission_denied")
    assert contact_mode(request, space, taking=False) is True
    switch(space, key, original=original)
    assert contact_mode(request, space, taking=True) is True

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
