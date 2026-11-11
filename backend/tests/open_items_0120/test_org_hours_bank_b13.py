"""Open item B13: the organization hours bank for organization (house/partner-event) bookings.

Written, not run: the consolidation lane runs it with the isolated Docker stack.
Authentication is forced (`force_authenticate`), so the route-class gate of the token layer is not exercised here.
"""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.bookings import organization_hours as bank
from apps.bookings import organization_hours_admin as service
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger
from apps.bookings.organization_booking import book_for_organization
from apps.bookings.services_staff_edit import edit_booking_time
from apps.bookings.services_transitions import cancel_booking
from apps.bookings.staff_price_confirmation import preview
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from apps.payments.pricing.errors import PriceChanged
from rest_framework.exceptions import ValidationError
from tests.bookings.test_included_hours_221d import slot
from tests.bookings.test_staff_price_confirmation import booking_debts
from tests.machines.certification_helpers import _manager, _member, _space
from tests.payments.pricing.helpers import rate

pytestmark = pytest.mark.django_db
D = Decimal
FEATURE = "bookings.organization_bookings"
ON = {FEATURE, "bookings.staff_tools", "charges.enabled", "charges.bookings", "charges.pricing"}


def world(slug, *, minutes=180, period="none", features=ON):
    maker = _space(slug, modules=("bookings",), certifications=False)
    maker.enabled_features = sorted(set(maker.enabled_features) | set(features))
    maker.save(update_fields=["enabled_features"])
    rate(maker, "bookings", per_hour="10.00")
    manager, _ = _manager(maker, slug + "-desk", actions=(Action.MANAGE_BOOKINGS,))
    contact, _ = _member(maker, slug + "-contact")
    org = Organization.objects.create(name="Partner Org", slug=f"{slug}-org")
    OrganizationMakerspace.objects.create(organization=org, makerspace=maker, relationship="affiliate")
    OrganizationMembership.objects.create(organization=org, user=contact, status="active")
    room = BookableSpace.objects.create(makerspace=maker, name="Room", approval_mode="instant")
    if minutes is not None:
        service.update_allowance(maker, org, manager, allowance_minutes=minutes, period=period)
    return maker, manager, contact, org, room


def book(room, manager, contact, org, *, day=3, hours=2):
    start, end = slot(day, hours)
    return book_for_organization(manager, room, org, contact, starts_at=start, ends_at=end)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def remaining(maker, org):
    return service.state(maker, org)["remaining_minutes"]


def rows(booking, entry):
    return OrganizationHoursLedger.objects.filter(booking=booking, entry=entry)


def test_bank_hours_are_consumed_before_any_charge():
    maker, manager, contact, org, room = world("oh-full", minutes=180)
    booking = book(room, manager, contact, org, hours=2)
    assert booking.status == Booking.Status.CONFIRMED
    assert not booking_debts(maker).exists()  # 2h <= 3h bank: nothing owed
    row = rows(booking, "consume").get()
    assert (row.minutes, row.organization_id, row.period_key) == (-120, org.pk, "all")
    assert remaining(maker, org) == 60
    assert AuditLog.objects.filter(makerspace=maker, action="booking.org_hours_consumed").count() == 1


def test_a_partly_covered_booking_charges_only_the_remainder():
    maker, manager, contact, org, room = world("oh-partial", minutes=60)
    booking = book(room, manager, contact, org, hours=2)
    assert booking_debts(maker).get(subject_id=booking.pk).amount == D("10.00")  # 1 banked hour + 1 priced hour
    assert rows(booking, "consume").get().minutes == -60
    assert remaining(maker, org) == 0


def test_no_allowance_or_a_zero_allowance_draws_nothing_and_charges_in_full():
    for slug, minutes in (("oh-none", None), ("oh-zero", 0)):
        maker, manager, contact, org, room = world(slug, minutes=minutes)
        booking = book(room, manager, contact, org, hours=2)
        assert booking_debts(maker).get(subject_id=booking.pk).amount == D("20.00")
        assert not OrganizationHoursLedger.objects.filter(booking=booking).exists()


def test_the_contacts_own_plan_hours_are_never_used_for_an_organization_booking():
    maker, manager, contact, org, room = world("oh-member-plan", minutes=60)
    booking = book(room, manager, contact, org, hours=1)
    assert OrganizationHoursLedger.objects.filter(booking=booking).count() == 1
    assert not booking.included_hours.exists()  # no member-term ledger row


def test_cancel_returns_the_hours_exactly_once():
    maker, manager, contact, org, room = world("oh-cancel", minutes=180)
    booking = book(room, manager, contact, org, hours=2)
    cancel_booking(booking, actor=manager)
    assert remaining(maker, org) == 180
    release = rows(booking, "release").get()
    assert (release.minutes, release.reverses_id) == (120, rows(booking, "consume").get().pk)
    assert bank.release(booking, manager) is None  # a second release is a no-op
    assert rows(booking, "release").count() == 1
    assert AuditLog.objects.filter(makerspace=maker, action="booking.org_hours_released").count() == 1


def test_restore_seam_takes_the_hours_again_as_the_next_generation():
    maker, manager, contact, org, room = world("oh-restore", minutes=180)
    booking = book(room, manager, contact, org, hours=2)
    cancel_booking(booking, actor=manager)
    Booking.objects.filter(pk=booking.pk).update(status=Booking.Status.CONFIRMED, cancelled_at=None)
    booking.refresh_from_db()
    row = bank.consume(booking, actor=manager)  # exactly what `restore_booking` calls
    assert (row.minutes, row.generation) == (-120, 2)
    assert remaining(maker, org) == 60


def test_a_shorter_time_edit_rebalances_down():
    maker, manager, contact, org, room = world("oh-down", minutes=180)
    booking = book(room, manager, contact, org, hours=2)
    start, end = slot(5, 1)
    edit_booking_time(booking, actor=manager, starts_at=start, ends_at=end)
    assert bank.live_consumption(booking).minutes == -60
    assert remaining(maker, org) == 120
    assert rows(booking, "release").count() == 1 and rows(booking, "consume").count() == 2


def test_a_longer_time_edit_needs_confirmation_then_rebalances_up():
    maker, manager, contact, org, room = world("oh-up", minutes=180)
    booking = book(room, manager, contact, org, hours=1)
    start, end = slot(5, 3)
    with pytest.raises(PriceChanged) as changed:
        edit_booking_time(booking, actor=manager, starts_at=start, ends_at=end)
    assert bank.live_consumption(booking).minutes == -60  # rolled back, untouched
    digest = changed.value.detail["confirmation"]["price_confirmation"]
    edit_booking_time(booking, actor=manager, starts_at=start, ends_at=end, price_confirmation=digest)
    assert bank.live_consumption(booking).minutes == -180
    assert remaining(maker, org) == 0


def test_the_balance_never_goes_negative_across_bookings():
    maker, manager, contact, org, room = world("oh-neg", minutes=180)
    book(room, manager, contact, org, day=3, hours=2)
    second = book(room, manager, contact, org, day=4, hours=2)
    assert rows(second, "consume").get().minutes == -60  # only the 1h left is banked
    assert booking_debts(maker).get(subject_id=second.pk).amount == D("10.00")
    assert remaining(maker, org) == 0


def test_preview_shows_the_organization_bank_and_matches_the_charge():
    maker, manager, contact, org, room = world("oh-preview", minutes=60)
    start, end = slot(3, 2)
    data = preview(room, contact, start, end, True, org)
    assert data["included_hours"]["source"] == "organization" and data["included_hours"]["applied_minutes"] == 60
    assert data["quote"]["total"] in ("10.00", "10.000", D("10.00"))


def test_grants_and_adjustments_move_the_pool_and_need_a_reason():
    maker, manager, contact, org, room = world("oh-adjust", minutes=60)
    service.adjust(maker, org, manager, entry="grant", minutes=60, reason="Sponsorship")
    assert service.state(maker, org)["pool_minutes"] == 120
    for bad in ({"reason": " ", "minutes": 5, "entry": "adjust"}, {"reason": "x", "minutes": 0, "entry": "adjust"},
                {"reason": "x", "minutes": -500, "entry": "adjust"}, {"reason": "x", "minutes": -5, "entry": "grant"}):
        with pytest.raises(ValidationError):
            service.adjust(maker, org, manager, **bad)
    booking = book(room, manager, contact, org, hours=2)
    assert not booking_debts(maker).exists() and rows(booking, "consume").get().minutes == -120
    assert AuditLog.objects.filter(makerspace=maker, action="organization.hours_adjusted").count() == 1


def test_period_keys_and_reset_boundaries():
    at = datetime(2030, 12, 31, 23, 30, tzinfo=dt_timezone.utc)
    assert bank.period_key("none", at) == "all" and bank.period_key("yearly", at) == "2030"
    assert bank.period_key("monthly", at) == "2030-12"
    assert bank.period_ends_at("monthly", at).startswith("2031-01-01")
    assert bank.period_ends_at("yearly", at).startswith("2031-01-01") and bank.period_ends_at("none", at) == ""


def test_ledger_rows_are_append_only():
    maker, manager, contact, org, room = world("oh-append", minutes=60)
    row = service.adjust(maker, org, manager, entry="grant", minutes=30, reason="Top-up")
    with pytest.raises(RuntimeError):
        row.save()
    with pytest.raises(RuntimeError):
        row.delete()


def test_staff_routes_read_set_and_adjust_with_audit():
    maker, manager, contact, org, room = world("oh-api", minutes=None)
    client = client_for(manager)
    base = f"/api/v1/admin/makerspace/{maker.pk}/organizations/{org.pk}/hours-bank/"
    assert client.get(base).data["configured"] is False
    patched = client.patch(base, {"allowance_minutes": 300, "period": "monthly"}, format="json")
    assert patched.status_code == 200 and patched.data["allowance_minutes"] == 300 and patched.data["period"] == "monthly"
    assert AuditLog.objects.filter(makerspace=maker, action="organization.hours_allowance_updated").count() == 1
    assert client.patch(base, {}, format="json").status_code == 400
    posted = client.post(base + "ledger/", {"entry": "grant", "minutes": 60, "reason": "Sponsor"}, format="json")
    assert posted.status_code == 201 and posted.data["actor_name"]
    assert client.post(base + "ledger/", {"entry": "adjust", "minutes": 5, "reason": ""}, format="json").status_code == 400
    page = client.get(base + "ledger/")
    assert page.status_code == 200 and page.data["count"] == 1 and set(page.data) >= {"next", "previous", "results"}


def test_scoping_other_space_unlinked_org_and_plain_member_cannot_reach_staff_routes():
    maker, manager, contact, org, room = world("oh-scope", minutes=60)
    other, other_manager, _c, other_org, _r = world("oh-scope-other", minutes=60)
    base = f"/api/v1/admin/makerspace/{maker.pk}/organizations/{org.pk}/hours-bank/"
    assert client_for(other_manager).get(base).status_code == 404
    assert client_for(other_manager).patch(base, {"allowance_minutes": 1}, format="json").status_code == 404
    assert client_for(manager).get(f"/api/v1/admin/makerspace/{maker.pk}/organizations/{other_org.pk}/hours-bank/").status_code == 404
    assert client_for(contact).get(base).status_code in (403, 404)
    assert client_for(contact).post(base + "ledger/", {"entry": "grant", "minutes": 5, "reason": "x"}, format="json").status_code in (403, 404)
    assert OrganizationHoursAllowance.objects.get(makerspace=maker, organization=org).allowance_minutes == 60


def test_the_routes_vanish_when_organization_bookings_is_off():
    maker, manager, contact, org, room = world("oh-off", minutes=60, features=ON - {FEATURE})
    response = client_for(manager).get(f"/api/v1/admin/makerspace/{maker.pk}/organizations/{org.pk}/hours-bank/")
    assert response.status_code in (400, 403, 404)
    assert bank.quote_allowance(maker, room, org, {"starts_at": slot(3, 1)[0]}) is None


def test_organization_admins_read_only_their_own_organization():
    maker, manager, contact, org, room = world("oh-orgadmin", minutes=120)
    book(room, manager, contact, org, hours=1)
    OrganizationMembership.objects.filter(organization=org, user=contact).update(
        governance_actions=["manage_organization_profile"])
    client = client_for(contact)
    own = client.get(f"/api/v1/admin/organizations/{org.pk}/hours-bank/")
    assert own.status_code == 200 and own.data["banks"][0]["makerspace_id"] == maker.pk
    assert own.data["banks"][0]["remaining_minutes"] == 60 and own.data["banks"][0]["makerspace_name"]
    ledger = client.get(f"/api/v1/admin/organizations/{org.pk}/hours-bank/{maker.pk}/ledger/")
    assert ledger.status_code == 200 and ledger.data["count"] == 1 and "actor_name" not in ledger.data["results"][0]
    assert client.patch(f"/api/v1/admin/makerspace/{maker.pk}/organizations/{org.pk}/hours-bank/",
                        {"allowance_minutes": 9999}, format="json").status_code in (403, 404)


def test_an_admin_of_another_organization_or_a_plain_org_member_gets_not_found():
    maker, manager, contact, org, room = world("oh-orgother", minutes=120)
    other_org = Organization.objects.create(name="Other", slug="oh-orgother-other")
    OrganizationMembership.objects.create(organization=other_org, user=contact, status="active",
                                          governance_actions=["manage_organization_members"])
    client = client_for(contact)
    assert client.get(f"/api/v1/admin/organizations/{org.pk}/hours-bank/").status_code == 404  # plain member of org
    assert client.get(f"/api/v1/admin/organizations/{org.pk}/hours-bank/{maker.pk}/ledger/").status_code == 404
    assert client.get(f"/api/v1/admin/organizations/{other_org.pk}/hours-bank/").data == {"banks": []}
