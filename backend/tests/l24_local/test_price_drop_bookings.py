"""#163A bookings: a lowered room price previews, then opens one staff-approved case per paid upcoming booking."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from apps.payments.models import Payment, PriceOverride, Refund, RefundCase
from tests.l24_local.helpers import D, cases, client, l24_space, opened_rows, preview
from tests.payments.refund_case_helpers import booking, member

pytestmark = pytest.mark.django_db


def room_url(room):
    return reverse("admin-bookable-space-detail", kwargs={"pk": room.pk})


def test_preview_lists_paid_upcoming_bookings_and_rolls_the_save_back():
    space, sm = l24_space("l24-bk-preview", modules=("bookings",))
    row, payment = booking(space, member("l24-bk-preview-m", space), amount="30.00")
    report = preview(client(sm).patch(room_url(row.space) + "?price_drop_preview=1", {"payment_amount": "20.00"},
                                      format="json"))
    assert report["count"] == 1 and report["truncated"] is False
    item = report["items"][0]
    assert (item["item_type"], item["item_id"], item["payment_id"]) == ("booking", row.pk, payment.pk)
    assert (D(item["before"]), D(item["after"]), D(item["difference"])) == (D("30.00"), D("20.00"), D("10.00"))
    assert report["totals"] == [{"currency": "usd", "difference": "10.00"}]
    # Nothing was written: the price, the cases and the audit trail are as before.
    assert BookableSpace.objects.get(pk=row.space_id).payment_amount == D("30.00")
    assert not RefundCase.objects.exists() and not opened_rows()
    assert not AuditLog.objects.filter(action="booking.space_updated").exists()


def test_save_opens_one_case_per_paid_upcoming_booking_and_refunds_nothing():
    space, sm = l24_space("l24-bk-save", modules=("bookings",))
    row, payment = booking(space, member("l24-bk-save-m", space), amount="30.00")
    used, used_payment = booking(space, member("l24-bk-save-u", space), amount="30.00")
    room = BookableSpace.objects.get(pk=used.space_id)
    Booking.objects.filter(pk=used.pk).update(starts_at=timezone.now() - timedelta(hours=3),
                                              ends_at=timezone.now() - timedelta(hours=2))
    response = client(sm).patch(room_url(row.space), {"payment_amount": "18.00"}, format="json")
    assert response.status_code == 200, response.data
    [case] = cases()
    assert case.payment_id == payment.pk and case.reason_code == "price_drop" and case.status == "open"
    assert case.due_amount == D("12.00") and case.kind == "due"
    share = case.policy_snapshot["shares"][0]
    assert share["source"] == "price_drop" and share["item"] == f"booking:{row.pk}" and share["after"] == "18.00"
    assert not Refund.objects.exists()  # never automatic
    assert Payment.objects.get(pk=payment.pk).status == "paid_offline"
    [audit] = opened_rows("bookings")
    assert audit.meta["case_ids"] == [case.pk] and audit.meta["payment_ids"] == [payment.pk]
    assert AuditLog.objects.filter(action="payment.refund_case_opened", meta__case_id=case.pk).exists()
    # The past booking on its own room is untouched by a change to that room.
    client(sm).patch(room_url(room), {"payment_amount": "5.00"}, format="json")
    assert not RefundCase.objects.filter(payment=used_payment).exists()


def test_repeat_save_offers_nothing_and_a_second_drop_only_the_rest():
    space, sm = l24_space("l24-bk-twice", modules=("bookings",))
    row, payment = booking(space, member("l24-bk-twice-m", space), amount="30.00")
    client(sm).patch(room_url(row.space), {"payment_amount": "20.00"}, format="json")
    client(sm).patch(room_url(row.space), {"payment_amount": "25.00"}, format="json")  # a rise: nothing
    client(sm).patch(room_url(row.space), {"payment_amount": "20.00"}, format="json")  # back to 20: nothing
    assert RefundCase.objects.get().due_amount == D("10.00")
    client(sm).patch(room_url(row.space), {"payment_amount": "15.00"}, format="json")
    case = RefundCase.objects.get()
    assert case.due_amount == D("15.00") and len(case.policy_snapshot["shares"]) == 2
    assert len(opened_rows()) == 2


def test_a_rise_charges_nothing_more_and_opens_nothing():
    space, sm = l24_space("l24-bk-rise", modules=("bookings",))
    row, payment = booking(space, member("l24-bk-rise-m", space), amount="30.00")
    report = preview(client(sm).patch(room_url(row.space) + "?price_drop_preview=1", {"payment_amount": "45.00"},
                                      format="json"))
    assert report["count"] == 0
    assert client(sm).patch(room_url(row.space), {"payment_amount": "45.00"}, format="json").status_code == 200
    assert not RefundCase.objects.exists()
    payment.refresh_from_db()
    assert payment.amount == D("30.00") and Payment.objects.filter(subject_id=row.pk).count() == 1


def test_switch_off_means_no_cases_and_no_preview():
    space, sm = l24_space("l24-bk-off", on=False, modules=("bookings",))
    row, _ = booking(space, member("l24-bk-off-m", space), amount="30.00")
    refused = client(sm).patch(room_url(row.space) + "?price_drop_preview=1", {"payment_amount": "10.00"},
                               format="json")
    assert refused.status_code == 404
    assert BookableSpace.objects.get(pk=row.space_id).payment_amount == D("30.00")
    assert client(sm).patch(room_url(row.space), {"payment_amount": "10.00"}, format="json").status_code == 200
    assert not RefundCase.objects.exists() and not opened_rows()


def test_rate_card_and_item_override_saves_reach_bookings():
    from tests.payments.pricing.helpers import rate
    space, sm = l24_space("l24-bk-card", modules=("bookings",))
    rate(space, "bookings", per_booking="40.00")
    # The room's own price is 0 (inherit), so the space card charges 40.
    paid_row, paid = booking(space, member("l24-bk-card-p", space), amount="0.00")
    assert paid.amount == D("40.00")
    url = f"/api/v1/admin/makerspace/{space.pk}/pricing/overrides/{PriceOverride.TargetType.BOOKABLE_SPACE}/{paid_row.space_id}"
    report = preview(client(sm).put(url + "?price_drop_preview=1",
                                    {"component": "per_booking", "mode": "custom", "amount": "25.00"}, format="json"))
    assert [D(item["difference"]) for item in report["items"]] == [D("15.00")]
    card = f"/api/v1/admin/makerspace/{space.pk}/pricing/bookings"
    response = client(sm).put(card, {"lines": [{"component": "per_booking", "amount": "32.00"}]}, format="json")
    assert response.status_code == 200, response.data
    case = RefundCase.objects.get(payment=paid)
    assert case.due_amount == D("8.00") and case.reason_code == "price_drop"
