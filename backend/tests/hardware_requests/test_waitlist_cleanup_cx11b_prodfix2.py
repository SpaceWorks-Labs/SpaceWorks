"""537: leaving an offered place releases its hold without offering or notifying off."""
import pytest
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests.models_loans import LoanWaitlistEntry
from tests.accounts.account_factories import make_membership, make_staff
from tests.modules.switch_matrix_object_helpers import client_for, object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.operations.route_support_cx11b_g4 import send, snapshot
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["loans.waitlist", "notifications"])
def test_offered_waitlist_cleanup_releases_only_owners_hold_without_notifying(native, key, monkeypatch):
    space, client, _ = object_world(native)
    owner = User.objects.get(username="sx-real-object-manager")
    peer = make_staff(space, username="cleanup-waitlist-peer", access_status="active")
    make_membership(owner, space)
    make_membership(peer, space)
    peer_client = client_for(peer, space, native)
    product = make_product(space, total_quantity=1, available_quantity=0, reserved_quantity=1, issued_quantity=0)
    entry = LoanWaitlistEntry.objects.create(makerspace=space, product=product, user=owner,
        quantity=1, held_quantity=1, status="offered")
    kept = LoanWaitlistEntry.objects.create(makerspace=space, product=product, user=peer, quantity=1)
    sent = []
    monkeypatch.setattr("apps.hardware_requests.notifications_loans.notify_waitlist_offer",
                        lambda row: sent.append(row.pk))
    url = reverse("hardware_requests:member-loan-waitlist-leave", kwargs={"makerspace_id": space.pk, "pk": entry.pk})
    switch(space, key)
    before = snapshot()
    with no_domain_writes():
        refused = send(peer_client, "POST", url)
    assert response_pair(refused) == (404, "not_found")
    assert snapshot() == before
    baseline = AuditLog.objects.count()
    with TestCase.captureOnCommitCallbacks(execute=True):
        response = send(client, "POST", url)
    assert response_pair(response) == (200, None)
    entry.refresh_from_db()
    kept.refresh_from_db()
    product.refresh_from_db()
    assert (entry.user_id, entry.status, entry.held_quantity) == (owner.pk, "cancelled", 0)
    assert entry.closed_at is not None
    assert (kept.user_id, kept.status, kept.held_quantity, kept.offered_at, kept.closed_at) == (
        peer.pk, "waiting", 0, None, None)
    assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == (1, 0, 0)
    assert LoanWaitlistEntry.objects.filter(makerspace=space).count() == 2
    assert list(AuditLog.objects.order_by("pk").values_list("action", flat=True)[baseline:]) == [
        "inventory.waitlist_left"]
    assert sent == []
