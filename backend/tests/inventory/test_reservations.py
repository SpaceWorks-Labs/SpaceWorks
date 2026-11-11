"""Loan waitlist holds (inventory D3/D14): FIFO offers, claims and lapses never oversell."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.hardware_requests import waitlist, workflow
from apps.hardware_requests.models_loans import LoanWaitlistEntry as Entry
from apps.hardware_requests.request_workflow import RequesterSnapshot
from apps.inventory.models import InventoryProduct
from tests.return_helpers import make_member, make_product, make_space


def space_with(slug, *features):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled", "loans.waitlist",
                                                                         *features})
    space.save(update_fields=["enabled_features"])
    return space


def submit(space, member, product, quantity=1, **extra):
    snapshot = RequesterSnapshot(username=member.username, name="", email="", phone="")
    return workflow.submit_request(space, [{"product": product, "quantity": quantity}], "",
                                   requester_principal=member, contact_snapshot=snapshot,
                                   audit_actor=member, **extra)


def member(space, username):
    from apps.accounts.models import User
    return make_member(username, space, membership_role="custom", role=User.Role.REQUESTER)


def stock(product):
    product.refresh_from_db()
    return product.available_quantity, product.reserved_quantity


@pytest.mark.django_db
def test_offers_hold_stock_in_order_and_a_claim_becomes_the_reservation(django_capture_on_commit_callbacks):
    space = space_with("wait-order")
    staff = make_member("wait-order-sm", space)
    product = make_product(space, available_quantity=1, total_quantity=1)
    holder = member(space, "wait-holder")
    first, second = member(space, "wait-first"), member(space, "wait-second")
    loan = workflow.accept_request(staff, submit(space, holder, product))
    one = waitlist.join(first, product, 1)
    two = waitlist.join(second, product, 1)
    assert (waitlist.position(one), waitlist.position(two)) == (1, 2)
    with pytest.raises(ValidationError):
        waitlist.join(first, product, 1)
    with django_capture_on_commit_callbacks(execute=True):
        workflow.cancel_request(staff, loan, by_owner=False)
    one.refresh_from_db()
    two.refresh_from_db()
    assert (one.status, one.held_quantity, two.status) == ("offered", 1, "waiting")
    assert stock(product) == (0, 1)
    with django_capture_on_commit_callbacks(execute=True):
        claimed = submit(space, first, product, waitlist_entry_id=one.pk)
        workflow.accept_request(staff, claimed)
    one.refresh_from_db()
    assert one.status == "fulfilled" and one.held_quantity == 0
    assert stock(product) == (0, 1)


@pytest.mark.django_db
def test_an_unclaimed_offer_lapses_and_moves_to_the_next(django_capture_on_commit_callbacks):
    space = space_with("wait-lapse")
    product = make_product(space, available_quantity=0, total_quantity=1, issued_quantity=1)
    first, second = member(space, "lapse-first"), member(space, "lapse-second")
    one, two = waitlist.join(first, product, 1), waitlist.join(second, product, 1)
    with django_capture_on_commit_callbacks(execute=True):
        InventoryProduct.objects.filter(pk=product.pk).update(available_quantity=1, issued_quantity=0)
        waitlist.schedule_offers(product.pk)
    one.refresh_from_db()
    assert one.status == "offered"
    with django_capture_on_commit_callbacks(execute=True):
        assert waitlist.lapse_due_offers(now=timezone.now() + timedelta(days=3)) == 1
    one.refresh_from_db()
    two.refresh_from_db()
    assert (one.status, two.status, two.held_quantity) == ("lapsed", "offered", 1)
    assert stock(product) == (0, 1)


@pytest.mark.django_db
def test_switch_off_refuses_join_and_offers_nothing():
    space = make_space("wait-off")
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    product = make_product(space, available_quantity=0, total_quantity=1, issued_quantity=1)
    with pytest.raises(Exception):
        waitlist.join(member(space, "wait-off-m"), product, 1)
    assert waitlist.offer_next(product.pk) == []


@pytest.mark.django_db(transaction=True)
def test_concurrent_offers_and_accepts_never_drive_stock_below_zero():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = space_with("wait-race")
    staff = make_member("wait-race-sm", space)
    product = make_product(space, available_quantity=1, total_quantity=1)
    entry = Entry.objects.create(makerspace=space, product=product, user=member(space, "race-w"),
                                 quantity=1)
    pending = submit(space, member(space, "race-r"), product)
    start = Barrier(2)

    def offer():
        close_old_connections()
        try:
            start.wait(timeout=15)
            return waitlist.offer_next(product.pk)
        finally:
            close_old_connections()

    def accept():
        close_old_connections()
        try:
            start.wait(timeout=15)
            try:
                workflow.accept_request(staff, pending)
                return "accepted"
            except Exception as exc:  # InsufficientStock surfaces as a workflow error
                return type(exc).__name__
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=30) for future in (pool.submit(offer), pool.submit(accept))]
    available, reserved = stock(product)
    assert available >= 0 and reserved <= 1 and available + reserved == 1
    entry.refresh_from_db()
    assert (entry.status == "offered") != (results[1] == "accepted")
