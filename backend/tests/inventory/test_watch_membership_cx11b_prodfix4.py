"""Watch membership errors use the shared mapper and leave another person's watch intact."""
import pytest
from django.urls import reverse

from apps.inventory.models_watch import InventoryWatch
from tests.inventory.switch_support_cx11b_p1 import snapshot
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.payments.account_helpers import make_payer
from tests.return_helpers import authenticated_client, make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


@pytest.mark.parametrize("method", ["post", "delete"])
@pytest.mark.parametrize("state", ["on", "off", "restored"])
@pytest.mark.parametrize("key", ["public_inventory", "loans.enabled",
                                 "inventory.notify_when_back", "notifications"])
def test_nonmember_watch_refusal_is_typed_and_preserves_the_owners_watch(method, state, key):
    space = live_space("watch-mapping-target", MODULE_KEYS)
    other = live_space("watch-mapping-other", MODULE_KEYS)
    owner = make_payer("watch-mapping-owner", space)
    stranger = make_payer("watch-mapping-stranger", other)
    client = authenticated_client(stranger)
    product = make_product(space, total_quantity=1, available_quantity=0, issued_quantity=1)
    watch = InventoryWatch.objects.create(makerspace=space, product=product, user=owner)
    if state != "on":
        original = switch(space, key)
        if state == "restored":
            switch(space, key, original=original)
    objects = {"product": product, "watch": watch}
    before = snapshot(objects)
    url = reverse("v1:public-inventory-watch", kwargs={"makerspace_slug": space.slug, "pk": product.pk})
    with no_domain_writes():
        response = getattr(client, method)(url, {}, format="json")
    public_off = state == "off" and key in {"public_inventory", "loans.enabled"}
    expected = (404, "module_disabled") if public_off else (403, "membership_required")
    assert response_pair(response) == expected, response.data
    if public_off:
        assert response.data["module"] == "public_inventory"
    assert snapshot(objects) == before
    assert list(InventoryWatch.objects.values_list("product_id", "user_id")) == [(product.pk, owner.pk)]
