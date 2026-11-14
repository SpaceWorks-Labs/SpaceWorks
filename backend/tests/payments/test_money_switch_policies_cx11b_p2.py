"""Charge/rail keys are routeless policies consumed by every charge seam, not fake URLs."""
from decimal import Decimal

import pytest

from apps.makerspaces.models import MakerspaceMembership
from apps.payments.availability import CHARGE_DOMAINS, charge_tracking_enabled, charges_tracked, online_payments_enabled
from apps.payments.models import Payment
from apps.payments.services import create_payment
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.payments.account_helpers import make_payer
from tests.payments.money_subject_cx11b_p2 import subject
from tests.payments.switch_helpers_cx11b_p2 import read_policy_cycle, switch
from tests.payments.test_models import configured_settings

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger, pytest.mark.area_payments]


@pytest.mark.parametrize("domain", CHARGE_DOMAINS)
@pytest.mark.parametrize("master", [False, True])
def test_charge_policy_hides_only_the_selected_debt_domain_and_keeps_existing_money(domain, master):
    space = live_space("p2-charge", MODULE_KEYS)
    person = make_payer("p2-charge-person", space)
    member = MakerspaceMembership.objects.get(makerspace=space, user=person)
    payment = create_payment(makerspace=space, subject_type="makerspace_membership", subject_id=member.pk,
        member=person, amount=Decimal("12.50"), currency="usd", created_by=person)
    key = "charges.enabled" if master else f"charges.{domain}"
    expected = {name: True for name in CHARGE_DOMAINS}
    off = {name: False if master or name == domain else True for name in CHARGE_DOMAINS}
    read_policy_cycle(space, {"debt": payment}, key, lambda: charges_tracked(space), expected, off)
    # Removing the rail must never disable the debt policy, with credentials absent too.
    original = switch(space, "payments")
    assert charge_tracking_enabled(space, domain) is True
    assert online_payments_enabled(space, domain) is False
    assert Payment.objects.get(pk=payment.pk).amount == Decimal("12.50")
    switch(space, "payments", original=original)


@pytest.mark.parametrize("domain", CHARGE_DOMAINS)
@pytest.mark.parametrize("key_kind", ["domain", "master", "module"])
def test_online_policy_changes_new_debt_vendor_without_erasing_the_ledger(domain, key_kind):
    space = live_space("p2-rail", MODULE_KEYS)
    credentials = configured_settings(space)  # sk_test only; no provider request is made.
    key = {"domain": f"payments.{domain}", "master": "payments.enabled", "module": "payments"}[key_kind]
    subjects = [subject(space, domain) for _ in range(3)]

    def raise_debt(number):
        kind, row, person = subjects[number]
        return create_payment(makerspace=space, subject_type=kind, subject_id=row.pk,
            member=person, amount=Decimal("12.50"), currency="usd", created_by=person)

    first = raise_debt(0)
    assert (first.provider, first.status, first.online_rail) == ("stripe", "pending", None)
    read_policy_cycle(space, {"debt": first, "credentials": credentials, "subject": subjects[0][1]}, key,
                      lambda: online_payments_enabled(space, domain), True, False)
    original = switch(space, key)
    assert charge_tracking_enabled(space, domain) is True
    second = raise_debt(1)
    assert (second.provider, second.status, second.online_rail) == ("unclaimed", "pending", None)
    switch(space, key, original=original)
    third = raise_debt(2)
    assert (third.provider, third.status, third.online_rail) == ("stripe", "pending", None)
    assert Payment.objects.get(pk=second.pk).provider == "unclaimed"
    assert Payment.objects.get(pk=first.pk).amount == Decimal("12.50")
    # The money master controls recording policy independently of the online rail.
    original = switch(space, "charges.enabled")
    assert charge_tracking_enabled(space, domain) is False
    assert online_payments_enabled(space, domain) is True
    switch(space, "charges.enabled", original=original)


@pytest.mark.parametrize("domain,parent", [("bookings", "bookings"), ("events", "events"),
    ("machines", "machines"), ("membership", "membership"), ("shop", "shop")])
def test_charge_domain_policy_requires_its_own_module_but_not_the_payment_rail(domain, parent):
    space = live_space("p2-money-parent", MODULE_KEYS)
    kind, row, person = subject(space, domain)
    payment = create_payment(makerspace=space, subject_type=kind, subject_id=row.pk, member=person,
        amount=Decimal("12.50"), currency="usd", created_by=person)
    read_policy_cycle(space, {"subject": row, "debt": payment}, parent,
        lambda: charge_tracking_enabled(space, domain), True, False)


@pytest.mark.parametrize("domain,sibling", [("machines", "machine_service"), ("donations", "finance.donations")])
def test_online_rail_also_requires_its_domain_sibling_without_disabling_debt_tracking(domain, sibling):
    space = live_space("p2-money-sibling", MODULE_KEYS)
    credentials = configured_settings(space)
    kind, row, person = subject(space, domain)
    payment = create_payment(makerspace=space, subject_type=kind, subject_id=row.pk, member=person,
        amount=Decimal("12.50"), currency="usd", created_by=person)
    read_policy_cycle(space, {"subject": row, "debt": payment, "credentials": credentials}, sibling,
        lambda: online_payments_enabled(space, domain), True, False)
    assert charge_tracking_enabled(space, domain) is True
