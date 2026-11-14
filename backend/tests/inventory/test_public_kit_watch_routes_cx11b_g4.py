"""Published kits and personal availability watches use their actual public/member contracts."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventory.equipment_kit_services import create_template
from apps.inventory.models_watch import InventoryWatch
from tests.accounts.account_factories import make_membership, make_staff
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cleanup_cycle, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["public_inventory", "request_workflow", "loans.enabled"])
@pytest.mark.parametrize("name", ["hardware_requests:equipment-kit-public-list", "hardware_requests:equipment-kit-public-detail"])
def test_published_kit_restores_its_version_and_exact_public_lines(native, key, name):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    space.enabled_modules = [module for module in space.enabled_modules if module != "membership"]
    space.public_site_enabled = True
    space.save(update_fields=["enabled_modules", "public_site_enabled"])
    product = make_product(space)
    template, version = create_template(actor=actor, makerspace_id=space.pk, name="Retained kit",
        lines=[{"product_id": product.pk, "kind": "returnable", "quantity_per_person": 2}])
    template.published_for_contexts = True
    template.save(update_fields=["published_for_contexts"])
    kwargs = {"makerspace_slug": space.slug}
    if name.endswith("detail"):
        kwargs["kit_id"] = template.pk
    url = reverse(name, kwargs=kwargs)
    expected = {"id": template.pk, "name": "Retained kit", "version": 1,
        "lines": [{"product_id": product.pk, "display_name": product.name, "quantity_per_person": 2, "kind": "returnable"}]}

    def check(response):
        assert (response.data if name.endswith("detail") else response.data["results"]) == (expected if name.endswith("detail") else [expected])
        version.refresh_from_db()
        assert version.lines == [{"product_id": product.pk, "kind": "returnable", "quantity_per_person": 2}]
    hidden = key == "request_workflow"
    def empty(response):
        assert response.data["results"] == []
    # Public kit endpoints require a personal account. Anonymous access keeps its 401;
    # this is not the makerspace-addressed staff contract from 481/494.
    cycle(space, key, lambda: client.get(url), check,
          off=(200, None) if hidden and name.endswith("list") else (404, "not_found" if hidden else "module_disabled"),
          off_check=empty if hidden and name.endswith("list") else None, refusal_key="public_inventory",
          foreign=lambda: APIClient().get(url), foreign_pair=(401, "not_authenticated"))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["public_inventory", "loans.enabled", "inventory.notify_when_back", "notifications"])
@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_watch_route_changes_only_the_callers_watch_and_retains_it_off(native, key, method):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    from apps.presence.models import PresenceSession
    from django.utils import timezone
    from datetime import timedelta
    PresenceSession.objects.create(makerspace=space, member=actor,
        started_at=timezone.now(), expires_at=timezone.now() + timedelta(hours=2))
    product = make_product(space, available_quantity=0, issued_quantity=1, total_quantity=1)
    if method == "DELETE":
        InventoryWatch.objects.create(makerspace=space, product=product, user=actor)
    url = reverse("v1:public-inventory-watch", kwargs={"makerspace_slug": space.slug, "pk": product.pk})
    foreign = outsider(native)
    def check(response):
        assert InventoryWatch.objects.filter(product=product, user=actor).count() == (1 if method == "POST" else 0)
        if method == "POST":
            assert response.data == {"subscribed": True}
            watch = InventoryWatch.objects.get(product=product, user=actor)
            assert (watch.ready_at, watch.notified_at) == (None, None)
    module = key in {"public_inventory", "loans.enabled"}
    off = (404, "module_disabled" if module else "feature_disabled")
    # Public inventory lookup gates first, then require_active_member. A non-member's
    # 403 is the declared member contract; it is not rewritten to a staff-route 404.
    pair = lambda disabled: ((403, "permission_denied") if native else
                             off if disabled and module else (403, "membership_required"))
    if method == "DELETE" and key in {"inventory.notify_when_back", "notifications"}:
        peer = make_staff(space, username="g4-kept-watch-owner", access_status="active")
        make_membership(peer, space)
        kept = InventoryWatch.objects.create(makerspace=space, product=product, user=peer)
        def cleanup_check(response):
            check(response)
            kept.refresh_from_db()
            assert (kept.user_id, kept.product_id, kept.ready_at, kept.notified_at) == (peer.pk, product.pk, None, None)
        cleanup_cycle(space, key, lambda: send(client, method, url), cleanup_check, on=(204, None),
            foreign=[(lambda: send(foreign, method, url),
                      (403, "permission_denied") if native else (403, "membership_required"))],
            audit=("inventory.watch_unsubscribed",))
        return
    cycle(space, key, lambda: send(client, method, url), check, on=(200 if method == "POST" else 204, None),
          off=off, refusal_key="public_inventory" if module else "inventory.notify_when_back",
          foreign=lambda: send(foreign, method, url), foreign_pair=pair,
          audit=("inventory.watch_subscribed" if method == "POST" else "inventory.watch_unsubscribed",))
