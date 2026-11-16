"""Real charge seams are inert off and resume on the SAME domain subject, with no rail."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import MakerspacePaymentSettings, Payment
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import retained
from tests.payments.money_subject_cx11b_p2 import subject
from tests.payments.switch_helpers_cx11b_p2 import domain_rows, no_policy_writes, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


def prepare(space, domain, actor):
    kind, row, person = subject(space, domain)
    if domain == "bookings":
        from apps.bookings.models import Booking
        from apps.bookings.service_payments import create_for_confirmed_booking
        room = row.space
        room.payment_amount = Decimal("12.50")
        room.save(update_fields=["payment_amount"])
        return row, lambda: create_for_confirmed_booking(Booking.objects.select_related("space__makerspace", "member").get(pk=row.pk), actor)
    if domain == "events":
        from apps.events.models import EventRegistration
        from apps.events.service_payments import create_for_registered_registration
        row.quoted_amount = Decimal("12.50")
        row.save(update_fields=["quoted_amount"])
        return row, lambda: create_for_registered_registration(EventRegistration.objects.select_related("event__makerspace", "member").get(pk=row.pk), actor)
    if domain == "machines":
        from apps.machines.models import Machine, MachineServiceRequest, MakerspaceMachineTypePricing
        from apps.machines.service_payments import create_for_completed_request
        machine = Machine.objects.create(makerspace=space, machine_type=row.queue.machine_type, name="Retained printer")
        MakerspaceMachineTypePricing.objects.create(makerspace=space, machine_type=row.queue.machine_type,
            flat_fee=Decimal("12.50"), rate_per_unit=0, payment_enabled=True)
        row.assigned_machine = machine
        row.save(update_fields=["assigned_machine"])
        return row, lambda: create_for_completed_request(MachineServiceRequest.objects.select_related("makerspace", "assigned_machine__machine_type", "member").get(pk=row.pk), actor)
    if domain == "membership":
        from apps.makerspaces.membership_term_charges import raise_term_start
        plan = MembershipPlan.objects.create(makerspace=space, name="Retained term plan", interval="monthly",
            amount=Decimal("12.50"), currency="usd")
        term = MembershipTerm.objects.create(membership=row, plan=plan, starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30), price=Decimal("12.50"), currency="usd")
        return term, lambda: raise_term_start(actor, MembershipTerm.objects.select_related("membership__makerspace", "membership__user", "plan").get(pk=term.pk))
    from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
    from apps.hardware_requests.loan_payments import raise_deposit
    from tests.return_helpers import make_product
    assert domain == "loans"
    # These are initial-state billing fixtures; no request transition is performed here.
    loan = HardwareRequest.objects.create(makerspace=space, requester=person, requester_username=person.username, status="issued")
    item = make_product(space)
    HardwareRequestItem.objects.create(request=loan, product=item, requested_quantity=1,
        accepted_quantity=1, issued_quantity=1)
    policy = MakerspacePaymentSettings.objects.get(makerspace=space)
    policy.loan_deposit_mode, policy.loan_deposit_amount = "fixed", Decimal("12.50")
    policy.save(update_fields=["loan_deposit_mode", "loan_deposit_amount"])
    return loan, lambda: raise_deposit(loan.pk, actor)


@pytest.mark.parametrize("domain", ["loans", "machines", "bookings", "events", "membership"])
@pytest.mark.parametrize("master", [False, True])
def test_charge_seam_attempts_no_sql_off_and_raises_one_unclaimed_debt_after_restoring(domain, master):
    space = live_space("p2-seam", set(MODULE_KEYS) - {"payments"})
    actor = make_staff(space, username="p2-seam-manager", access_status="active")
    MakerspacePaymentSettings.objects.create(makerspace=space, default_currency="usd")
    row, charge = prepare(space, domain, actor)
    key = "charges.enabled" if master else f"charges.{domain}"
    before, rows = retained({"subject": row}), domain_rows()
    original = switch(space, key)
    with no_policy_writes():
        assert charge() is None
    assert retained({"subject": row}) == before and domain_rows() == rows
    assert Payment.objects.filter(makerspace=space).count() == 0
    switch(space, key, original=original)
    payment = charge()
    assert payment is not None
    assert (payment.status, payment.provider, payment.amount, payment.currency) == (
        "pending", "unclaimed", Decimal("12.50"), "usd")
    assert charge().pk == payment.pk
    assert Payment.objects.filter(makerspace=space).count() == 1
    before = retained({"subject": row, "payment": payment})
    original = switch(space, key)
    with no_policy_writes():
        assert charge() is None
    assert retained({"subject": row, "payment": payment}) == before
    switch(space, key, original=original)
    assert charge().pk == payment.pk
    assert retained({"subject": row, "payment": payment}) == before
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="payment.created").count() == 1


@pytest.mark.parametrize("domain", ["shop", "donations"])
@pytest.mark.parametrize("master", [False, True])
def test_sales_and_gifts_refuse_money_off_then_record_once_after_restoring(domain, master):
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.identity import Donor
    from apps.payments.donations.services import create_gift
    from apps.shop.errors import ShopRefused
    from apps.shop.orders_core import order_payment
    from apps.shop.services_pos import pos_sale
    from tests.shop.helpers import line, product
    from tests.payments.account_helpers import make_payer

    space = live_space("p2-money-sale", set(MODULE_KEYS) - {"payments"})
    actor = make_staff(space, username="p2-money-seller", access_status="active")
    person = make_payer("p2-money-giver", space)
    MakerspacePaymentSettings.objects.create(makerspace=space, default_currency="usd")
    # A cash drawer is a sibling requirement for cash sales; leave it off to isolate tracking.
    switch(space, "shop.cash_up")
    row, variant = product(space, actor, price="12.50", stock=8)
    donor = Donor(person, "Retained giver", person.email, person)
    def create():
        if domain == "shop":
            order = pos_sale(space, actor=actor, lines=[line(variant)], method="cash", reference="P2-OFFLINE")
            return order, order_payment(order)
        return create_gift(space, donor, amount=Decimal("12.50"))
    objects = {"product": row, "variant": variant}
    before, rows = retained(objects), domain_rows()
    key = "charges.enabled" if master else f"charges.{domain}"
    original = switch(space, key)
    error_type, status = (ShopRefused, 409) if domain == "shop" else (DonationRefused, 400)
    with no_policy_writes(), pytest.raises(error_type) as error:
        create()
    assert (error.value.status_code, str(error.value.detail["code"])) == (status, "charges_off")
    assert retained(objects) == before and domain_rows() == rows
    switch(space, key, original=original)
    created, payment = create()
    assert (payment.provider, payment.amount, payment.currency) == ("unclaimed", Decimal("12.50"), "usd")
    assert payment.status == ("paid_offline" if domain == "shop" else "pending")
    if domain == "shop":
        receipt = payment.manual_settlements.get()
        assert (receipt.method, receipt.reference) == ("cash", "P2-OFFLINE")
    before = retained({"subject": created, "payment": payment, **objects})
    original = switch(space, key)
    with no_policy_writes(), pytest.raises(error_type) as error:
        create()
    assert (error.value.status_code, str(error.value.detail["code"])) == (status, "charges_off")
    assert retained({"subject": created, "payment": payment, **objects}) == before
    switch(space, key, original=original)
    assert retained({"subject": created, "payment": payment, **objects}) == before
    if domain == "donations":
        assert create()[1].pk == payment.pk
    assert Payment.objects.filter(makerspace=space).count() == 1
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="payment.created").count() == 1
