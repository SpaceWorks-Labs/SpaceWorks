"""Waiver tools disappear while off; recorded entitlement survives without an online rail."""
from decimal import Decimal

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.payments.models_pricing_rules import LoanFeeWaiver
from apps.payments.pricing.waivers import waived_components
from apps.payments.services import create_payment
from apps.payments.availability import charge_tracking_enabled
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import client_for
from tests.modules.test_switch_matrix_objects_rest_support import switch
from tests.return_helpers import make_member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("rail", [False, True], ids=["rail-off", "rail-on"])
@pytest.mark.parametrize("tracking", ["on", "charges.enabled", "charges.loans"])
@pytest.mark.parametrize("key", ["loans.fee_waivers", "request_workflow"])
def test_fee_waiver_tools_restore_existing_entitlement_with_optional_rail(native, rail, tracking, key):
    space, _, _, product, loan, _, _ = setup_loan("p1-waiver")
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.fee_waivers"})
    space.enabled_modules = sorted(set(space.enabled_modules) | {"payments"})
    space.save(update_fields=["enabled_features", "enabled_modules"])
    if not rail:
        switch(space, "payments")
    actor = make_member("p1-waiver-manager", space)
    assert charge_tracking_enabled(space, "loans") is True
    payment = create_payment(makerspace=space, subject_type="loan_rental", subject_id=loan.pk,
        member=loan.requester, amount=Decimal("15.00"), currency="usd", created_by=actor,
        pricing_snapshot={"gross": "15.00", "currency": "usd"})
    assert (payment.provider, payment.status, payment.amount) == ("unclaimed", "pending", Decimal("15.00"))
    if tracking != "on":
        switch(space, tracking)
        assert charge_tracking_enabled(space, "loans") is False
    waiver = LoanFeeWaiver.objects.create(makerspace=space, request=loan, created_by=actor,
        components=["late"], reason="Documented late-fee exemption")
    url = reverse("loan-fee-waivers", kwargs={"makerspace_id": space.pk, "request_id": loan.pk})
    from tests.payments.route_support_cx11b_g5 import foreign_client
    foreign = foreign_client(native)
    from tests.accounts.account_factories import make_staff
    peer = make_staff(space, username="p1-waiver-no-loan-authority", role_slug="technician", access_status="active")
    peer_client = client_for(peer, space, native)
    prove_route(space, client_for(actor, space, native),
                {"loan": loan, "product": product, "waiver": waiver, "payment": payment},
                key, lambda c: c.get(url), off=(404, "pricing_disabled"),
                check=lambda r: _same_waiver(r, waiver.pk),
                outsiders=[(foreign, (403, "permission_denied") if native else (404, "not_found")),
                           (peer_client, (404, "not_found"))])
    original = switch(space, "loans.fee_waivers")
    assert set(waived_components(loan)) == {"late"}
    payment.refresh_from_db()
    assert (payment.provider, payment.status, payment.amount) == ("unclaimed", "pending", Decimal("15.00"))
    assert payment.pricing_snapshot == {"gross": "15.00", "currency": "usd"}
    switch(space, "loans.fee_waivers", original=original)
    assert set(waived_components(loan)) == {"late"}


def _same_waiver(response, pk):
    assert [row["id"] for row in response.data] == [pk]

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
