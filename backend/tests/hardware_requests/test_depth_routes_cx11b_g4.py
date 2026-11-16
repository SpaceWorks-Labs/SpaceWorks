"""Loan owner, waitlist and settings routes pin effects and each actual dependency."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanReservationPolicy, LoanWaitlistEntry
from tests.accounts.account_factories import make_membership, make_staff
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import cleanup_cycle, contains, cycle, outsider, rows, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]

CASES = [(name, method, key) for name, method, keys in [
    ("hardware_requests:member-request-withdraw", "POST", ("request_workflow", "loans.enabled", "loans.withdrawals")),
    ("hardware_requests:member-loan-waitlist", "GET", ("request_workflow", "loans.enabled", "loans.waitlist", "notifications")),
    ("hardware_requests:member-loan-waitlist", "POST", ("request_workflow", "loans.enabled", "loans.waitlist", "notifications")),
    ("hardware_requests:member-loan-waitlist-leave", "POST", ("request_workflow", "loans.enabled", "loans.waitlist", "notifications")),
    ("hardware_requests:staff-loan-waitlist", "GET", ("request_workflow", "loans.enabled", "loans.waitlist", "notifications")),
    ("hardware_requests:admin-loan-reservation-policy", "GET", ("request_workflow", "loans.enabled")),
    ("hardware_requests:admin-loan-reservation-policy", "PUT", ("request_workflow", "loans.enabled")),
] for key in keys]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method,key", CASES)
def test_loan_depth_route_effect_retention_and_standing(native, name, method, key):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    product = make_product(space, total_quantity=1, available_quantity=0, issued_quantity=1)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
                                         status="pending_approval")
    entry = None
    if not (name == "hardware_requests:member-loan-waitlist" and method == "POST"):
        entry = LoanWaitlistEntry.objects.create(makerspace=space, product=product, user=actor, quantity=1)
    policy = LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=12)
    kwargs = {"makerspace_id": space.pk}
    if name == "hardware_requests:member-request-withdraw":
        kwargs["pk"] = row.pk
    if name == "hardware_requests:member-loan-waitlist-leave":
        kwargs["pk"] = entry.pk
    url = reverse(name, kwargs=kwargs)
    body = {"product_id": product.pk} if name == "hardware_requests:member-loan-waitlist" and method == "POST" else {}
    if method == "PUT":
        body = {"pickup_window_hours": 24}
    actions = ()
    if name == "hardware_requests:member-request-withdraw":
        body, actions = {"reason": "Plans changed"}, ("request.cancelled",)
    elif method == "PUT":
        actions = ("settings.changed",)
    elif method == "POST":
        actions = ("inventory.waitlist_left" if name.endswith("leave") else "inventory.waitlist_joined",)

    def check(response):
        if name == "hardware_requests:member-request-withdraw":
            row.refresh_from_db()
            assert (row.status, row.closed_by_id) == ("cancelled", actor.pk)
        elif name == "hardware_requests:admin-loan-reservation-policy":
            policy.refresh_from_db()
            expected = 24 if method == "PUT" else 12
            assert policy.pickup_window_hours == expected
            assert response.data == {"pickup_window_hours": expected, "reservation_max_days_ahead": 30, "waitlist_offer_hours": 48}
        elif method == "GET":
            contains(response, entry.pk)
            assert (rows(response)[0]["product"], rows(response)[0]["quantity"], rows(response)[0]["position"]) == (product.pk, 1, 1)
        else:
            saved = LoanWaitlistEntry.objects.get(pk=response.data["id"])
            assert (saved.user_id, saved.product_id, saved.quantity, saved.status) == (
                actor.pk, product.pk, 1, "cancelled" if name.endswith("leave") else "waiting")
            assert LoanWaitlistEntry.objects.filter(makerspace=space).count() == (2 if name.endswith("leave") else 1)
            if name.endswith("leave"):
                assert saved.closed_at is not None
                peer_entry.refresh_from_db()
                assert (peer_entry.status, peer_entry.closed_at, peer_entry.held_quantity) == ("waiting", None, 0)
    module = key in {"request_workflow", "loans.enabled"}
    off = (404, "module_disabled" if module else "feature_disabled")
    foreign = outsider(native)
    probe = lambda: send(foreign, method, url, body)
    pair = (404, "not_found")
    if name.startswith("hardware_requests:member"):
        # Personal collections have no grant of tenant authority (494); an active account's
        # own empty collection is readable. Object non-owners stay concealed (520).
        peer = make_staff(space, username="g4-depth-peer", access_status="active")
        make_membership(peer, space)
        peer_client = client_for(peer, space, native)
        if method == "GET":
            def probe():
                response = send(peer_client, method, url, body)
                if response.status_code == 200:
                    assert response.data == []
                return response
            pair = lambda disabled: off if disabled else (200, None)
        elif name == "hardware_requests:member-loan-waitlist":
            # Joining is a personal command open to any eligible member. Use a hidden
            # foreign product as the no-standing subject instead of forbidding a peer.
            other_product = make_product(space, name="Hidden waitlist item", is_public=False)
            probe = lambda: send(peer_client, method, url, {"product_id": other_product.pk})
            pair = lambda disabled: off if disabled else (404, "not_found")
        else:
            probe = lambda: send(peer_client, method, url, body)
    if name.endswith("leave"):
        peer_entry = LoanWaitlistEntry.objects.create(makerspace=space, product=product, user=peer, quantity=1)
    if name.endswith("leave") and key in {"loans.waitlist", "notifications"}:
        cleanup_cycle(space, key, lambda: send(client, method, url, body), check, on=(200, None),
            foreign=[(probe, (404, "not_found")),
                     (lambda: send(foreign, method, url, body), (403, "permission_denied") if native else (404, "not_found"))],
            audit=actions)
        return
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if name == "hardware_requests:member-loan-waitlist" and method == "POST" else 200, None),
          off=off, refusal_key="request_workflow" if module else "loans.waitlist" if key == "notifications" else key,
          foreign=probe, foreign_pair=pair, foreign_native=native and not name.startswith("hardware_requests:member"), audit=actions)
