"""Pickup expiry uses the real workflow and releases reserved stock exactly once."""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from tests.modules.switch_matrix_object_helpers import object_world, retained
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, switch
from tests.return_helpers import make_member, make_product, make_user

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("key", ["loans.pickup_windows", "request_workflow"])
def test_expiry_worker_off_keeps_reservation_and_restore_releases_once(key):
    space, _, _ = object_world(False)
    actor, borrower = make_member("p1-expiry-manager", space), make_user("p1-expiry-borrower")
    product = make_product(space, total_quantity=2, available_quantity=2)
    loan = HardwareRequest.objects.create(makerspace=space, requester=borrower, requester_username=borrower.username)
    HardwareRequestItem.objects.create(request=loan, product=product, requested_quantity=1)
    loan = workflow.accept_request(actor, loan)
    now = timezone.now()
    loan.pickup_until = now - timedelta(minutes=1)
    loan.save(update_fields=["pickup_until"])
    objects = {"loan": loan, "product": product}
    before = retained(objects)
    original = switch(space, key)
    with connection.execute_wrapper(_no_write):
        assert workflow.expire_due_requests(now=now) == {"expired": 0, "skipped": 0, "lapsed": 0}
    assert retained(objects) == before
    switch(space, key, original=original)
    assert workflow.expire_due_requests(now=now) == {"expired": 1, "skipped": 0, "lapsed": 0}
    assert workflow.expire_due_requests(now=now) == {"expired": 0, "skipped": 0, "lapsed": 0}
    loan.refresh_from_db()
    product.refresh_from_db()
    assert loan.status == "expired"
    assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == (2, 0, 0)
    assert AuditLog.objects.filter(makerspace=space, action="request.expired", target_id=str(loan.pk)).count() == 1
