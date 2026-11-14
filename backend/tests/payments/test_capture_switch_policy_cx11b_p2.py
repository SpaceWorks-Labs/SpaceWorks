"""Capture policy is routeless: it holds mismatches, never stops recording real money."""
import pytest

from apps.payments.models import PaymentCaptureFlag, PaymentDocument, Refund
from tests.l5_local.test_capture_flags import _online, _paid
from tests.modules.switch_matrix_object_helpers import retained
from tests.payments.switch_helpers_cx11b_p2 import route_cycle, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger, pytest.mark.area_payments]


def test_capture_policy_resumes_holds_after_restoring_and_keeps_existing_flags_decidable():
    space, actor, first = _online("p2-capture", "100.00", "billing.capture_flags")
    _paid(space, "p2-capture", "evt_p2_first", 9000)
    flag = PaymentCaptureFlag.objects.get(payment=first)
    assert flag.kind == "mismatch" and flag.captured_minor == 9000
    assert PaymentDocument.objects.filter(payment=first, kind="receipt").count() == 0
    before = retained({"payment": first, "flag": flag})
    original = switch(space, "billing.capture_flags")
    # Ingest still claims provider event IDs; this policy must never stop settlement.
    _paid(space, "p2-capture", "evt_p2_first", 9000)
    assert retained({"payment": first, "flag": flag}) == before
    from tests.l5_local.helpers import dues
    second = dues(space, first.member, provider="stripe")
    from apps.payments.models import Payment
    Payment.objects.filter(pk=second.pk).update(stripe_checkout_session_id="cs_p2_second")
    _paid(space, "p2_second", "evt_p2_second", 9000)
    assert PaymentCaptureFlag.objects.filter(payment=second).count() == 0
    assert PaymentDocument.objects.filter(payment=second, kind="receipt").count() == 1
    switch(space, "billing.capture_flags", original=original)
    third = dues(space, first.member, provider="stripe")
    Payment.objects.filter(pk=third.pk).update(stripe_checkout_session_id="cs_p2_third")
    _paid(space, "p2_third", "evt_p2_third", 9000)
    assert PaymentCaptureFlag.objects.filter(payment=third, kind="mismatch").count() == 1
    assert PaymentDocument.objects.filter(payment=third, kind="receipt").count() == 0
    assert retained({"payment": first, "flag": flag}) == before
    assert Refund.objects.count() == 0


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["billing.capture_flags", "payments"])
def test_existing_held_capture_stays_visible_and_decidable_when_new_flagging_or_rail_is_off(native, key):
    from tests.modules.switch_matrix_object_helpers import client_for, response_pair
    from apps.payments.capture_flags import record_flag
    from tests.l5_local.helpers import dues, setup
    space, actor, payer = setup("p2-held", "billing.capture_flags")
    payment = dues(space, payer, provider="stripe")
    flag = record_flag(payment, kind="mismatch", provider="stripe", minor=9000, currency="inr")
    client = client_for(actor, space, native)
    url = f"/api/v1/admin/makerspace/{space.pk}/capture-flags"
    route_cycle(space, client, {"payment": payment, "flag": flag}, key, url,
        off=(200, None), check=lambda response: check_flag(response, flag))
    original = switch(space, key)
    result = client.post(url + f"/{flag.pk}/resolve", {"resolution": "acknowledged", "note": "Reviewed capture"}, format="json")
    assert response_pair(result) == (200, None), result.data
    assert PaymentCaptureFlag.objects.get(pk=flag.pk).resolution == "acknowledged"
    switch(space, key, original=original)


def check_flag(response, flag):
    assert response.data["count"] == 1 and response.data["results"][0]["id"] == flag.pk
