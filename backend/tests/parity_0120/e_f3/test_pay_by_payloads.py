"""E-F3: the pay-window deadline reaches the staff roster row and the guest's ticket (E-B5 C22)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.credentials.serializers_ticket import ProgrammeTicketSerializer
from apps.events.models import EventRegistration
from apps.events.serializers_registration_admin import EventRegistrationAdminSerializer
from tests.events.collab_helpers import make_member
from tests.parity_0120.e_b5.helpers import world

pytestmark = pytest.mark.django_db


def _registration(slug, pay_by):
    space, event, _staff = world(slug, "events.pay_window", amount="15")
    member = make_member(space, f"{slug}-guest")
    return EventRegistration.objects.create(event=event, member=member, name="Guest", email=member.email, phone="1",
                                            status="registered", pay_by=pay_by)


def test_staff_row_carries_the_open_pay_window():
    deadline = timezone.now() + timedelta(hours=24)
    data = EventRegistrationAdminSerializer(_registration("ef3-a", deadline)).data
    assert data["pay_by"] is not None


def test_staff_row_is_null_without_a_window():
    data = EventRegistrationAdminSerializer(_registration("ef3-b", None)).data
    assert data["pay_by"] is None


def test_ticket_schema_declares_pay_by_read_only():
    field = ProgrammeTicketSerializer().fields["pay_by"]
    assert field.read_only and field.allow_null
