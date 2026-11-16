"""Inactive booking resources cannot admit new contextual equipment proposals."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models_equipment_proposals import EquipmentProposalReceipt
from tests.bookings.staff_grant_helpers import client_for, grant_fixture
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import make_product


@pytest.mark.django_db(transaction=True)
def test_inactive_booking_resource_refuses_new_proposal_without_changing_history():
    maker, _manager, delegate, space, _grant, borrower = grant_fixture(
        "manage_reservations", slug="inactive-context-resource")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"loans.enabled"})
    maker.save(update_fields=["enabled_features"])
    start = timezone.now() + timedelta(days=1)
    booking = Booking.objects.create(space=space, member=borrower, name="Borrower", email=borrower.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    product = make_product(maker, is_public=True)
    url = reverse("hardware_requests:contextual-request-staff", args=[maker.pk])
    body = {"operation_id": str(uuid4()), "booking_id": booking.pk,
            "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
    with enabled_encryption():
        first = client_for(delegate).post(url, body, format="json")
        assert first.status_code == 201, first.content
        request_id = first.data["request_id"]
        space.is_active = False
        space.save(update_fields=["is_active"])
        product.refresh_from_db()
        before = (HardwareRequest.objects.count(), EquipmentProposalReceipt.objects.count(),
                  AuditLog.objects.count(), product.available_quantity, product.reserved_quantity)
        body["operation_id"] = str(uuid4())
        denied = client_for(delegate).post(url, body, format="json")
    product.refresh_from_db()
    assert denied.status_code == 404, denied.content
    assert before == (HardwareRequest.objects.count(), EquipmentProposalReceipt.objects.count(),
                      AuditLog.objects.count(), product.available_quantity, product.reserved_quantity)
    assert HardwareRequest.objects.filter(pk=request_id, requester=borrower).exists()
