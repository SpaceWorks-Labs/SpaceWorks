"""Owner histories, signed public tokens, and exact contractual renewal extensions."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, PublicToolLoan
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from tests.accounts.account_factories import make_membership, make_staff
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", [("hardware_requests:member-loan-renew", "loans.renewals"), ("hardware_requests:member-loan-renew", "request_workflow"),
    ("hardware_requests:member-loan-renew", "loans.enabled"), ("hardware_requests:member-loan-renew", "membership"),
    ("hardware_requests:staff-loan-renew", "loans.renewals"), ("hardware_requests:staff-loan-renew", "request_workflow"), ("hardware_requests:staff-loan-renew", "loans.enabled")])
def test_renewal_extends_the_same_request_and_linked_loan_exactly_once(native, name, key):
    from apps.hardware_requests.due_policy import effective_due
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    product = make_product(space, available_quantity=9, issued_quantity=1)
    due = timezone.now() + timedelta(days=2)
    policy = MakerspaceLoanPolicy.objects.create(makerspace=space, loan_renewal_mode="auto", loan_renewal_days=3)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
        status="issued", issued_at=timezone.now(), return_due_at=due)
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=1, accepted_quantity=1, issued_quantity=1)
    linked = PublicToolLoan.objects.create(makerspace=space, request=row, requester=actor, target_type="direct",
        target_id=row.pk, target_label=product.name, source="admin_direct", due_at=due)
    url = reverse(name, kwargs={"makerspace_id": space.pk, "pk": row.pk})
    expected = effective_due(space, due + timedelta(days=3))

    def check(response):
        row.refresh_from_db()
        linked.refresh_from_db()
        assert (row.renewal_count, row.return_due_at, linked.due_at) == (1, expected, expected)
        assert response.data["renewal_count"] == 1
        product.refresh_from_db()
        assert (product.available_quantity, product.issued_quantity) == (9, 1)
        policy.refresh_from_db()
        assert policy.loan_renewal_days == 3
    foreign = outsider(native)
    probes = []
    if name == "hardware_requests:member-loan-renew":
        peer = make_staff(space, username="g4-renewal-non-owner", access_status="active")
        peer_client = client_for(peer, space, native)
        probes.append((lambda: send(peer_client, "POST", url), (404, "not_found")))
    off = (404, "feature_disabled" if key == "loans.renewals" else "module_disabled")
    cycle(space, key, lambda: send(client, "POST", url), check, off=off,
          refusal_key="request_workflow" if key == "loans.enabled" else key,
          audit=("request.renewed",), foreign=lambda: send(foreign, "POST", url), foreign_native=native, extra_probes=probes)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["request_workflow", "loans.enabled"])
def test_personal_history_returns_only_the_callers_seeded_request(native, key):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    peer = make_staff(space, username="g4-other-borrower", access_status="active")
    product = make_product(space)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username, status="pending_approval")
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=2)
    other = HardwareRequest.objects.create(makerspace=space, requester=peer, requester_username=peer.username, status="pending_approval")
    url = reverse("hardware_requests:member-borrowing-history", kwargs={"makerspace_id": space.pk})
    peer_client = client_for(peer, space, native)

    def check(response):
        contains(response, row.pk)
        assert response.data["results"][0]["items"][0]["product_name"] == product.name
        assert "requester_contact_email" not in str(response.data)

    def probe():
        response = peer_client.get(url)
        if response.status_code == 200:
            contains(response, other.pk)
        return response
    # Personal collection: owner filtering, with the module refusal retained for members (494).
    cycle(space, key, lambda: client.get(url), check, refusal_key="request_workflow", foreign=probe,
          foreign_pair=lambda disabled: (404, "module_disabled") if disabled else (200, None))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["request_workflow", "loans.enabled"])
def test_existing_public_status_token_remains_readable_when_new_loans_are_off(native, key):
    from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
    from tests.modules.switch_matrix_object_helpers import response_pair
    from tests.operations.route_support_cx11b_g4 import snapshot
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username, status="accepted")
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=2)
    if native:
        client._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    url = reverse("hardware_requests:request-status", kwargs={"public_token": row.public_token})
    missing = reverse("hardware_requests:request-status", kwargs={"public_token": uuid4()})
    before = snapshot()
    saved = None
    for disabled in (False, True, False):
        if disabled:
            saved = switch(space, key)
        elif saved is not None:
            switch(space, key, original=saved)
        for caller in (client, APIClient()):
            with no_domain_writes():
                response = caller.get(url)
                absent = caller.get(missing)
            assert response_pair(response) == (200, None)
            assert response_pair(absent) == (404, "not_found")
            assert (response.data["status"], response.data["items"]) == ("accepted", [{"product_name": product.name, "requested_quantity": 2}])
            assert snapshot() == before
