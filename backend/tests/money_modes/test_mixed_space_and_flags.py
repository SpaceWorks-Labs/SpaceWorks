"""#184: a mixed space never leaks one domain's mode into another; the flags the UI reads (G5);
the capability shape behind them (G4, G9, G10)."""

from decimal import Decimal

import pytest

from apps.hardware_requests.models import RequesterAccountability
from apps.makerspaces.platform import bootstrap_payload
from apps.payments.availability import CHARGE_DOMAINS, charge_tracking_enabled, charges_tracked
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_damage_lost import damaged_return, url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.money_modes.helpers import FREE, OFFLINE, charges, master_off, set_mode
from tests.payments.pricing.helpers import client, pricing_space, rate
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


def test_free_lending_beside_paid_machines_and_bookings(django_capture_on_commit_callbacks):
    from apps.bookings.models import Booking
    from apps.machines.service_payments import create_for_completed_request
    from tests.payments.pricing.test_domain_seams import install
    from tests.payments.test_track3_booking_event_charging import bookable, create_booking, member_with_phone
    space, _ = pricing_space("mm-mixed")
    install(space, "bookings", "machines", "machine_service")
    staff = staff_account(space, "mm-mixed-staff", "space_manager")
    product = make_product(space, unit_cost=Decimal("40"))
    request = damaged_return(space, staff, product, callbacks=django_capture_on_commit_callbacks)
    set_mode(space, "loans", FREE)
    set_mode(space, "machines", OFFLINE)
    set_mode(space, "bookings", OFFLINE)

    flags = bootstrap_payload(space)["charges_tracked"]
    assert (flags["loans"], flags["machines"], flags["bookings"]) == (False, True, True)

    row = RequesterAccountability.objects.get(request=request)
    refused = client(staff).post(url(space, request, row), {"amount": "15.00"}, format="json")
    assert refused.status_code == 404 and refused.data["code"] == "charges_off"
    assert charges(space, "loan_damage") == []

    booking = create_booking(bookable(space, amount="9.00"), member_with_phone("mm-mixed-booker", space))
    assert booking.status == Booking.Status.CONFIRMED and len(charges(space, "booking")) == 1

    from apps.machines.models import Machine, MachineServiceRequest, MachineType, ServiceQueue
    rate(space, "machines", time="6.00")
    kind = MachineType.objects.create(makerspace=space, name="Printer", slug="mm-mixed-printer")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="P1")
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Queue")
    job = MachineServiceRequest.objects.create(queue=queue, makerspace=space, requester=staff, member=staff,
                                               title="Bracket", assigned_machine=machine, actual_minutes=30)
    assert create_for_completed_request(job, staff) is not None
    assert len(charges(space, "machine_service_request")) == 1


def test_the_bootstrap_flags_follow_every_domain_and_the_master_switch():
    space, _ = pricing_space("mm-flags")
    payload = bootstrap_payload(space)["charges_tracked"]
    assert set(payload) == set(CHARGE_DOMAINS) == {"loans", "machines", "bookings", "events", "membership", "shop",
                                                  "donations"}
    assert payload == {domain: charge_tracking_enabled(space, domain) for domain in CHARGE_DOMAINS}
    master_off(space)
    assert not any(charges_tracked(space).values())


def test_capability_shape_g4_g9_g10():
    from apps.makerspaces.capabilities import FEATURES, default_enabled_features
    assert FEATURES["charges.machines"].requires_modules == ()
    assert FEATURES["charges.machines"].parent_module == "machines"
    assert FEATURES["charges.shop"].parent_module == "shop"
    donations = FEATURES["charges.donations"]
    assert donations.parent_module is None and donations.default_enabled
    assert "charges.donations" in default_enabled_features()


def test_installing_a_module_brings_back_its_pruned_charge_tracking_key():
    from apps.makerspaces.module_install import install_module
    from tests.return_helpers import make_space
    space = make_space("mm-install")
    space.enabled_modules = sorted(set(space.enabled_modules) - {"bookings"})
    space.enabled_features = sorted(set(space.enabled_features) - {"charges.bookings"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    install_module(space, "bookings")
    space.refresh_from_db()
    assert "charges.bookings" in space.enabled_features
    assert charge_tracking_enabled(space, "bookings") is ("charges.enabled" in space.enabled_features)


def test_the_donations_backfill_turns_tracking_on_for_existing_spaces():
    import importlib

    from django.apps import apps as django_apps

    from apps.makerspaces.models import Makerspace
    from tests.return_helpers import make_space
    space = make_space("mm-backfill")
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_features=[key for key in space.enabled_features if key != "charges.donations"])
    migration = importlib.import_module("apps.makerspaces.migrations.0130_charges_donations_default_on")
    migration.enable(django_apps, None)
    space.refresh_from_db()
    assert "charges.donations" in space.enabled_features
