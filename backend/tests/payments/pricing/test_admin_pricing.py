"""Lane L15: staff pricing APIs -- authority, scoping, audit, impact, switches (A1, A9, A13, C-11d)."""

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models_settings_authority import ModuleSettingLock
from apps.payments.models import MakerspacePaymentSettings, PriceDiscount, PriceOverride, PricingDefault
from tests.fixed_roles.helpers import staff_account
from tests.payments.pricing.helpers import D, client, member, plan, pricing_space, switch
from tests.return_helpers import make_product, make_space

pytestmark = pytest.mark.django_db


def base(space):
    return f"/api/v1/admin/makerspace/{space.pk}/pricing"


@pytest.fixture
def setup():
    space, _ = pricing_space("adm-pricing", "charges.discounts")
    sm = staff_account(space, "adm-sm", "space_manager")
    im = staff_account(space, "adm-im", "inventory_manager")
    return space, sm, im


def test_space_manager_saves_lending_rates_and_the_legacy_block(setup):
    space, sm, _im = setup
    body = {"mode": "paid", "lines": [{"component": "rental_per_day", "amount": "2.00", "cap": "10.00"}],
            "lending": {"deposit_mode": "fixed", "deposit_amount": "15.00", "late_per_day": "1.50"}}
    response = client(sm).put(f"{base(space)}/loans", body, format="json")
    assert response.status_code == 200, response.data
    line = next(row for row in response.data["lines"] if row["component"] == "rental_per_day")
    assert (line["amount"], line["cap"]) == ("2.00", "10.00")
    settings_row = MakerspacePaymentSettings.objects.get(makerspace=space)
    assert (settings_row.loan_deposit_amount, settings_row.loan_late_fee_per_day) == (D("15.00"), D("1.50"))
    row = AuditLog.objects.get(action="settings.changed", meta__key="pricing.loans")
    assert row.meta["via"] == "space_manager" and row.meta["to"]["lending"]["deposit_amount"] == "15.00"


def test_inventory_manager_reads_lending_but_needs_a_grant_to_change_it(setup):
    space, _sm, im = setup
    response = client(im).get(f"{base(space)}/loans")
    assert response.status_code == 200 and response.data["editable"] is False
    assert response.data["rental_timing_editable"] is True
    refused = client(im).put(f"{base(space)}/loans", {"mode": "paid"}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"


def test_inventory_manager_changes_rental_timing_without_a_grant_but_not_past_a_lock(setup):
    space, sm, im = setup
    response = client(im).put(f"{base(space)}/loans/rental-timing", {"rental_timing": "at_return"}, format="json")
    assert response.status_code == 200, response.data
    assert PricingDefault.objects.get(makerspace=space, domain="loans").rental_timing == "at_return"
    audit = AuditLog.objects.get(action="settings.changed", meta__key="rental_timing")
    assert audit.meta["via"] == "fixed_exception" and audit.actor == im
    ModuleSettingLock.objects.create(makerspace=space, setting_key="rental_timing", locked_by=sm)
    locked = client(im).put(f"{base(space)}/loans/rental-timing", {"rental_timing": "at_checkout"}, format="json")
    assert locked.status_code == 403 and locked.data["code"] == "setting_locked"


def test_overrides_belong_to_whoever_edits_the_item_and_are_audited(setup):
    space, _sm, im = setup
    product = make_product(space)
    url = f"{base(space)}/overrides/inventory_product/{product.pk}"
    response = client(im).put(url, {"component": "rental_per_day", "mode": "custom", "amount": "3.00"},
                              format="json")
    assert response.status_code == 200, response.data
    row = PriceOverride.objects.get(product=product, component="rental_per_day")
    assert (row.mode, row.amount) == ("custom", D("3.00"))
    assert AuditLog.objects.filter(action="pricing.override_set", meta__target_id=product.pk).exists()
    deposit = client(im).put(url, {"component": "deposit", "mode": "custom", "amount": "7.00"}, format="json")
    assert deposit.status_code == 200
    product.refresh_from_db()
    assert product.deposit_amount == D("7.00")  # the item's own field holds its custom deposit
    events = staff_account(space, "adm-em", "event_manager")
    assert client(events).put(url, {"component": "rental_per_day", "mode": "free"}, format="json").status_code in (403, 404)
    cleared = client(im).put(url, {"component": "rental_per_day", "mode": "inherit"}, format="json")
    assert cleared.status_code == 200 and not PriceOverride.objects.filter(product=product).exists()
    assert AuditLog.objects.filter(action="pricing.override_cleared").exists()


def test_cross_space_items_are_not_found(setup):
    space, sm, _im = setup
    other = make_space("adm-other")
    foreign = make_product(other)
    url = f"{base(space)}/overrides/inventory_product/{foreign.pk}"
    assert client(sm).get(url).status_code == 404


def test_discounts_are_space_manager_only_and_member_scoped(setup):
    space, sm, im = setup
    buyer = member(space)
    pro = plan(space)
    body = {"name": "Members 10%", "audience": "all_members", "percent_bps": 1000}
    assert client(im).post(f"{base(space)}/discounts", body, format="json").status_code == 404
    created = client(sm).post(f"{base(space)}/discounts", body, format="json")
    assert created.status_code == 201, created.data
    plan_rule = client(sm).post(f"{base(space)}/discounts", {"name": "Pro", "audience": "plan", "plan": pro.pk,
                                                            "amount_off": "2.00"}, format="json")
    assert plan_rule.status_code == 201, plan_rule.data
    outsider = staff_account(make_space("adm-else"), "adm-else-sm", "space_manager")
    bad = client(sm).post(f"{base(space)}/discounts", {"name": "X", "audience": "member", "member": outsider.pk,
                                                       "percent_bps": 100}, format="json")
    assert bad.status_code == 400
    one = client(sm).post(f"{base(space)}/discounts", {"name": "Y", "audience": "member", "member": buyer.pk,
                                                       "percent_bps": 100}, format="json")
    assert one.status_code == 201, one.data
    archived = client(sm).post(f"{base(space)}/discounts/{created.data['id']}/archive", format="json")
    assert archived.status_code == 200 and archived.data["archived_at"]
    assert PriceDiscount.objects.filter(pk=created.data["id"]).exists()
    assert {row.action for row in AuditLog.objects.filter(action__startswith="pricing.discount")} == {
        "pricing.discount_created", "pricing.discount_archived"}


def test_impact_lists_inheriting_items_and_spares_custom_and_free(setup):
    space, sm, _im = setup
    inherit, custom = make_product(space, name="Inherits"), make_product(space, name="Custom")
    PriceOverride.objects.create(makerspace=space, domain="loans", component="rental_per_day",
                                 target_type="inventory_product", product=custom, mode="custom", amount=D("1.00"))
    body = {"mode": "paid", "lines": [{"component": "rental_per_day", "amount": "4.00"}]}
    response = client(sm).post(f"{base(space)}/loans/impact", body, format="json")
    assert response.status_code == 200, response.data
    moved = {(row["target_id"], row["component"]) for row in response.data["changes"]}
    assert (inherit.pk, "rental_per_day") in moved and (custom.pk, "rental_per_day") not in moved
    assert not PricingDefault.objects.filter(makerspace=space).exists()  # nothing saved


def test_currency_is_space_manager_only(setup):
    space, sm, im = setup
    assert client(im).put(f"{base(space)}/currency", {"default_currency": "inr"}, format="json").status_code == 404
    response = client(sm).put(f"{base(space)}/currency", {"default_currency": "INR"}, format="json")
    assert response.status_code == 200 and response.data["default_currency"] == "inr"


def test_switch_off_removes_the_surface(setup):
    space, sm, _im = setup
    switch(space, "charges.pricing", on=False)
    for path in ("loans", "loans/rental-timing", "currency", "discounts"):
        response = client(sm).get(f"{base(space)}/{path}")
        assert response.status_code == 404, path
    switch(space, "charges.pricing")
    switch(space, "charges.discounts", on=False)
    assert client(sm).get(f"{base(space)}/discounts").status_code == 404
    assert client(sm).get(f"{base(space)}/loans").status_code == 200


def test_membership_is_read_only_and_unknown_domains_404(setup):
    space, sm, _im = setup
    from apps.makerspaces.module_install import install_module
    install_module(space, "membership")
    assert client(sm).get(f"{base(space)}/membership").status_code == 200
    assert client(sm).put(f"{base(space)}/membership", {"mode": "paid"}, format="json").status_code == 400
    assert client(sm).get(f"{base(space)}/spaceships").data["code"] == "pricing_domain_unknown"
