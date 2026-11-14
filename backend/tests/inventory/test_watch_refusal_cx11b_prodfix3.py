"""P2: typed watch refusals preserve standing and the existing presence policy."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.inventory.models_watch import InventoryWatch
from apps.makerspaces.models import MakerspaceMembership
from apps.presence.models import PresenceSession
from tests.accounts.account_factories import make_membership, make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.operations.route_support_cx11b_g4 import outsider, send, snapshot
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


def watch_world(native):
    space = live_space("watch-p2", MODULE_KEYS)
    member = make_staff(space, username="watch-p2-member", access_status="active")
    make_membership(member, space)
    product = make_product(space, total_quantity=1, available_quantity=0, issued_quantity=1)
    url = reverse("v1:public-inventory-watch", kwargs={"makerspace_slug": space.slug, "pk": product.pk})
    return space, member, product, client_for(member, space, native), url


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_foreign_watch_refusal_is_typed_without_membership_or_domain_writes(native, method):
    space, member, product, _client, url = watch_world(native)
    kept = InventoryWatch.objects.create(makerspace=space, product=product, user=member)
    foreign = outsider(native)
    memberships = list(MakerspaceMembership.all_tracks.filter(makerspace=space).order_by("pk").values())
    before = snapshot()
    for phase in ("on", "off", "restored"):
        if phase == "off":
            original = switch(space, "inventory.notify_when_back")
        elif phase == "restored":
            switch(space, "inventory.notify_when_back", original=original)
        with no_domain_writes():
            response = send(foreign, method, url)
        assert response_pair(response) == (403, "permission_denied" if native else "membership_required")
        assert snapshot() == before
        assert list(MakerspaceMembership.all_tracks.filter(makerspace=space).order_by("pk").values()) == memberships
        kept.refresh_from_db()
        assert (kept.user_id, kept.product_id, kept.ready_at, kept.notified_at) == (
            member.pk, product.pk, None, None,
        )


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_in_space_watch_keeps_its_existing_no_presence_session_requirement(native, method):
    space, member, product, client, url = watch_world(native)
    if method == "DELETE":
        InventoryWatch.objects.create(makerspace=space, product=product, user=member)
    assert not PresenceSession.objects.filter(makerspace=space, member=member).exists()
    baseline = AuditLog.objects.count()
    response = send(client, method, url)
    assert response_pair(response) == (200 if method == "POST" else 204, None)
    assert InventoryWatch.objects.filter(product=product, user=member).count() == (1 if method == "POST" else 0)
    if method == "POST":
        assert response.data == {"subscribed": True}
    assert list(AuditLog.objects.order_by("pk").values_list("action", flat=True)[baseline:]) == [
        "inventory.watch_subscribed" if method == "POST" else "inventory.watch_unsubscribed",
    ]
    assert not PresenceSession.objects.filter(makerspace=space, member=member).exists()
