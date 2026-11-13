"""MOD-1 condition 3: two real actors on the same row/quantity -- exactly one winner, never below zero.

Each test starts two threads behind a barrier, each with its own DB connection, against the real
service entry points (request_workflow, operations.services). PostgreSQL row locks are required.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests import request_workflow
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.workflow_errors import InvalidTransition
from apps.inventory.availability import InsufficientStock
from apps.inventory.models import InventoryProduct
from apps.operations import services
from apps.operations.models import StockTransfer, StocktakeLedgerEntry, StocktakeSession
from tests.return_helpers import make_box, make_member, make_product, make_space, make_user
from tests.test_request_workflow import make_hardware_request

pytestmark = pytest.mark.django_db(transaction=True)


def _race(work, *args_per_thread):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    start = Barrier(len(args_per_thread))

    def run(args):
        close_old_connections()
        try:
            start.wait(timeout=15)
            try:
                return ("ok", work(*args))
            except Exception as exc:  # the loser's typed error is the assertion target
                return ("err", exc)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(args_per_thread)) as pool:
        return [f.result(timeout=60) for f in [pool.submit(run, a) for a in args_per_thread]]


def test_two_accepts_for_the_last_unit_have_one_winner_and_the_loser_gets_insufficient_stock():
    space = make_space("m1-cc-accept")
    admin = make_member("m1-cc-accept-admin", space)
    product = make_product(space, total_quantity=1, available_quantity=1)
    first = make_hardware_request(space, product, quantity=1)
    second = make_hardware_request(space, product, quantity=1)

    def accept(request_id):
        return request_workflow.accept_request(
            User.objects.get(pk=admin.pk), HardwareRequest.objects.get(pk=request_id))

    results = _race(accept, (first.pk,), (second.pk,))
    outcomes = sorted(kind for kind, _ in results)
    assert outcomes == ["err", "ok"]
    loser = next(value for kind, value in results if kind == "err")
    assert isinstance(loser, InsufficientStock), repr(loser)
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (0, 1)
    statuses = sorted(HardwareRequest.objects.filter(pk__in=[first.pk, second.pk]).values_list("status", flat=True))
    assert statuses == ["accepted", "pending_approval"]
    assert AuditLog.objects.filter(action="request.accepted").count() == 1


def test_two_accepts_of_the_same_request_reserve_once_and_the_loser_gets_invalid_transition():
    space = make_space("m1-cc-same")
    admin = make_member("m1-cc-same-admin", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_hardware_request(space, product, quantity=2)

    def accept(request_id):
        return request_workflow.accept_request(
            User.objects.get(pk=admin.pk), HardwareRequest.objects.get(pk=request_id))

    results = _race(accept, (request.pk,), (request.pk,))
    assert sorted(kind for kind, _ in results) == ["err", "ok"]
    assert isinstance(next(v for k, v in results if k == "err"), InvalidTransition)
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (3, 2)  # reserved once, not 4
    assert AuditLog.objects.filter(action="request.accepted").count() == 1


def test_two_stocktake_applies_adjust_stock_once_and_the_loser_is_told_it_is_already_applied():
    space = make_space("m1-cc-stocktake")
    root = make_user("m1-cc-stocktake-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    product = make_product(space, total_quantity=10, available_quantity=10)
    session = StocktakeSession.objects.create(
        makerspace=space, started_by=root, status=StocktakeSession.Status.COUNTING, approval_required=False)
    services.add_stocktake_line(root, session, {"product_id": product.pk, "counted_quantity": 6, "condition": "available"})
    services.complete_stocktake(root, StocktakeSession.objects.get(pk=session.pk))
    services.approve_stocktake(root, StocktakeSession.objects.get(pk=session.pk))
    session.refresh_from_db()
    assert session.status == StocktakeSession.Status.APPROVED

    def apply(session_id):
        return services.apply_stocktake_adjustments(
            User.objects.get(pk=root.pk), StocktakeSession.objects.get(pk=session_id))

    results = _race(apply, (session.pk,), (session.pk,))
    assert sorted(kind for kind, _ in results) == ["err", "ok"]
    loser = next(v for k, v in results if k == "err")
    assert isinstance(loser, ValidationError)
    assert "Only approved stocktakes can be applied." in str(loser.detail)
    product.refresh_from_db()
    assert (product.available_quantity, product.total_quantity) == (6, 6)  # -4 once, never -8
    assert StocktakeLedgerEntry.objects.filter(stocktake=session).count() == 1
    assert AuditLog.objects.filter(action="stocktake.adjustments_applied").count() == 1


def test_two_transfers_of_the_same_stock_have_one_winner_and_availability_never_goes_negative():
    source, dest = make_space("m1-cc-xfer-s"), make_space("m1-cc-xfer-d")
    root = make_user("m1-cc-xfer-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    product = make_product(source, "Clamp", total_quantity=4, available_quantity=4)
    data = {"destination_makerspace_id": dest.pk, "reason": "race",
            "lines": [{"product_id": product.pk, "quantity": 3}]}

    def transfer(_n):
        return services.apply_stock_transfer(User.objects.get(pk=root.pk), source, dict(data))

    results = _race(transfer, (1,), (2,))
    assert sorted(kind for kind, _ in results) == ["err", "ok"]
    loser = next(v for k, v in results if k == "err")
    assert isinstance(loser, ValidationError), repr(loser)
    product.refresh_from_db()
    assert (product.available_quantity, product.total_quantity) == (1, 1)
    assert InventoryProduct.objects.get(makerspace=dest, name="Clamp").available_quantity == 3
    assert StockTransfer.objects.count() == 1
    assert AuditLog.objects.filter(action="stock_transfer.applied").count() == 1
    assert AuditLog.objects.filter(action="stock_transfer.received").count() == 1
