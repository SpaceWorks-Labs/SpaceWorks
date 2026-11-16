"""Public expected-back disclosure and availability-watch policy preserve borrowed stock."""
from zoneinfo import ZoneInfo
from datetime import timedelta
from unittest.mock import patch

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.db import connection
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models import InventoryProduct
from apps.inventory.models_watch import InventoryWatch
from apps.inventory.notify_me import availability_rose
from tests.inventory.test_expected_back import setup
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import client_for, retained, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, no_domain_writes, switch
from tests.return_helpers import make_member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_expected_back_policy_hides_only_the_date_then_restores_the_same_loan(native):
    space, due = setup("p1-expected")
    actor = make_member("p1-expected-viewer", space)
    client = client_for(actor, space, native)
    product = InventoryProduct.objects.get(makerspace=space, name="Router")
    loan = HardwareRequest.objects.get(makerspace=space)
    before = retained({"product": product, "loan": loan})
    path = f"/api/v1/public/{space.slug}/inventory/"
    expected = timezone.localtime(due, ZoneInfo(space.timezone)).date().isoformat()
    for disabled in (False, True, False):
        if disabled:
            original = switch(space, "inventory.expected_back")
        elif "original" in locals():
            switch(space, "inventory.expected_back", original=original)
        with no_domain_writes():
            response = client.get(path)
        assert response_pair(response) == (200, None)
        assert response.json()["results"][0]["expected_back_on"] == (None if disabled else expected)
    assert retained({"product": product, "loan": loan}) == before
    prove_route(space, client, {"product": product, "loan": loan}, "public_inventory",
                lambda c: c.get(path), off=(404, "module_disabled"))


@pytest.mark.parametrize("key", ["inventory.notify_when_back", "public_inventory", "notifications", "loans.enabled"])
def test_notify_policy_off_never_latches_availability_and_on_rearms_retained_watch(key):
    space, _ = setup("p1-watch")
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.notify_when_back"})
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications"})
    space.save(update_fields=["enabled_features", "enabled_modules"])
    product = InventoryProduct.objects.get(makerspace=space, name="Router")
    actor = make_member("p1-watch-owner", space)
    watch = InventoryWatch.objects.create(makerspace=space, product=product, user=actor)
    before = retained({"product": product})
    # The quantity mutation belongs to availability; this hook receives its fresh result.
    product.available_quantity = 1
    original = switch(space, key)
    product.makerspace = space
    with connection.execute_wrapper(_no_write):
        availability_rose(product, previous=0)
    watch.refresh_from_db()
    assert watch.ready_at is None and watch.notified_at is None
    switch(space, key, original=original)
    product.makerspace = space
    now = timezone.now()
    with patch("apps.inventory.notify_me.timezone.now", return_value=now):
        availability_rose(product, previous=0)
    watch.refresh_from_db()
    assert (watch.ready_at, watch.notified_at) == (now, None)
    with patch("apps.inventory.notify_me.timezone.now", return_value=now + timedelta(minutes=1)):
        availability_rose(product, previous=0)
    watch.refresh_from_db()
    assert (watch.ready_at, watch.notified_at) == (now, None)
    assert retained({"product": product}) == before

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
