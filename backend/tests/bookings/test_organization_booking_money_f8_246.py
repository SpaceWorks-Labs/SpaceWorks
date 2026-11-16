"""Decision 246 (lane F8): money rules for organization bookings (223k): the contact is billed, never the
organization, the staff actor or another member, and a refused booking records no debt."""
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking, BookingOrganizationLink
from apps.bookings.organization_booking import book_for_organization
from apps.payments.models import Payment
from tests.bookings.test_organization_booking import _window, _world
from tests.payments.pricing.helpers import rate

pytestmark = pytest.mark.django_db(transaction=True)
CHARGE_FEATURES = {"charges.enabled", "charges.bookings", "charges.pricing"}


def _priced(slug, **world):
    tenant, manager, resource, member, org = _world(slug, **world)
    tenant.enabled_features = sorted(set(tenant.enabled_features or []) | CHARGE_FEATURES)
    tenant.save(update_fields=["enabled_features"])
    rate(tenant, "bookings", per_hour="10.00")
    return tenant, manager, resource, member, org


def _debts(tenant):
    return Payment.objects.filter(makerspace=tenant, subject_type=Payment.SubjectType.BOOKING)


def test_the_contact_member_owes_the_priced_booking_not_the_actor_or_the_organization():
    tenant, manager, resource, member, org = _priced("f8-obm-bill")
    booking = book_for_organization(manager, resource, org, member, **_window())
    debt = _debts(tenant).get(subject_id=booking.pk)
    assert debt.member_id == member.pk and debt.member_id != manager.pk
    assert debt.amount == Decimal("20.00")
    assert BookingOrganizationLink.objects.get(booking=booking).billed_member_id == member.pk
    assert not _debts(tenant).exclude(member=member).exists()


def test_no_debt_is_recorded_when_charge_tracking_is_off():
    tenant, manager, resource, member, org = _world("f8-obm-free")
    booking = book_for_organization(manager, resource, org, member, **_window())
    assert booking.status == Booking.Status.CONFIRMED
    assert not _debts(tenant).exists()


def test_a_refused_organization_booking_records_no_booking_link_or_debt():
    tenant, manager, resource, member, org = _priced("f8-obm-refused", contact_in_org=False)
    with pytest.raises(ValidationError):
        book_for_organization(manager, resource, org, member, **_window())
    assert not Booking.objects.filter(space=resource).exists()
    assert not BookingOrganizationLink.objects.exists()
    assert not _debts(tenant).exists()


def test_two_organization_bookings_create_two_separate_debts_for_the_same_contact():
    tenant, manager, resource, member, org = _priced("f8-obm-two")
    first = book_for_organization(manager, resource, org, member, **_window(3))
    second = book_for_organization(manager, resource, org, member, **_window(5))
    assert {first.pk, second.pk} == set(_debts(tenant).values_list("subject_id", flat=True))
    assert _debts(tenant).count() == 2


def test_another_spaces_ledger_is_untouched():
    tenant, manager, resource, member, org = _priced("f8-obm-iso-a")
    other = _priced("f8-obm-iso-b")[0]
    book_for_organization(manager, resource, org, member, **_window())
    assert _debts(tenant).count() == 1 and not _debts(other).exists()
