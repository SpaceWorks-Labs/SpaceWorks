"""#163A tickets: a lowered ticket or event price opens a case per paid seat for an event not yet held."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, EventRegistration, EventTicketType
from apps.events.orders_pricing import paid_ticket_price
from apps.payments.models import Payment, Refund, RefundCase
from tests.l24_local.helpers import client, l24_space, opened_rows, preview
from tests.payments.refund_case_helpers import charge, member, paid_event, registration

pytestmark = pytest.mark.django_db
D = Decimal
MODULES = ("events",)
FEATURES = ("events.ticket_types",)


def sold_ticket(space, slug, *, amount="20.00", starts_in=timedelta(days=3), paid=True):
    event = paid_event(space, starts_in=starts_in, amount="0.00")
    ticket = EventTicketType.objects.create(makerspace=space, event=event, name="Standard", amount=D(amount))
    user = member(f"{slug}-m", space)
    row = registration(event, user)
    EventRegistration.objects.filter(pk=row.pk).update(ticket_type=ticket, quoted_amount=D(amount))
    row.refresh_from_db()
    status = Payment.Status.PAID_OFFLINE if paid else Payment.Status.PENDING
    payment = charge(space, user, subject_id=row.pk, amount=amount, status=status)
    return event, ticket, row, payment


def ticket_url(ticket):
    return reverse("admin-event-ticket-detail", kwargs={"pk": ticket.pk})


def test_lowering_a_sold_ticket_previews_and_opens_one_case_per_paid_seat():
    space, sm = l24_space("l24-tk-drop", modules=MODULES, features=FEATURES)
    event, ticket, row, payment = sold_ticket(space, "l24-tk-drop")
    _, _, _, unpaid = sold_ticket(space, "l24-tk-unpaid", paid=False)
    report = preview(client(sm).patch(ticket_url(ticket) + "?price_drop_preview=1", {"amount": "15.00"},
                                      format="json"))
    assert [(item["item_id"], item["difference"]) for item in report["items"]] == [(row.pk, "5.00")]
    assert EventTicketType.objects.get(pk=ticket.pk).amount == D("20.00")
    response = client(sm).patch(ticket_url(ticket), {"amount": "15.00"}, format="json")
    assert response.status_code == 200, response.data
    case = RefundCase.objects.get()
    assert (case.payment_id, case.reason_code, case.due_amount) == (payment.pk, "price_drop", D("5.00"))
    assert case.area == "events" and not Refund.objects.exists()
    assert opened_rows("events")[0].meta["case_ids"] == [case.pk]
    # The seat now stands at what is left after the offer (L6's frozen-price contract).
    assert paid_ticket_price(row)[0] == D("15.00")


def test_switch_off_keeps_a_sold_ticket_price_frozen():
    space, sm = l24_space("l24-tk-off", on=False, modules=MODULES, features=FEATURES)
    _, ticket, _, _ = sold_ticket(space, "l24-tk-off")
    refused = client(sm).patch(ticket_url(ticket), {"amount": "15.00"}, format="json")
    assert refused.status_code == 409 and refused.data["code"] == "ticket_type_referenced"
    assert client(sm).patch(ticket_url(ticket) + "?price_drop_preview=1", {"amount": "15.00"},
                            format="json").status_code == 409
    assert not RefundCase.objects.exists()


def test_a_sold_ticket_can_never_be_raised():
    space, sm = l24_space("l24-tk-rise", modules=MODULES, features=FEATURES)
    _, ticket, _, _ = sold_ticket(space, "l24-tk-rise")
    refused = client(sm).patch(ticket_url(ticket), {"amount": "25.00"}, format="json")
    assert refused.status_code == 409 and not RefundCase.objects.exists()


def test_an_event_already_held_is_not_re_priced():
    space, sm = l24_space("l24-tk-held", modules=MODULES, features=FEATURES)
    event, ticket, _, _ = sold_ticket(space, "l24-tk-held")
    Event.objects.filter(pk=event.pk).update(starts_at=timezone.now() - timedelta(hours=1))
    assert client(sm).patch(ticket_url(ticket), {"amount": "10.00"}, format="json").status_code == 200
    assert not RefundCase.objects.exists()


def test_lowering_an_event_price_reaches_seats_without_a_ticket_type():
    space, sm = l24_space("l24-ev-drop", modules=MODULES)
    event = paid_event(space, amount="20.00")
    user = member("l24-ev-drop-m", space)
    row = registration(event, user)
    EventRegistration.objects.filter(pk=row.pk).update(quoted_amount=D("20.00"))
    payment = charge(space, user, subject_id=row.pk, amount="20.00")
    url = reverse("admin-event-detail", kwargs={"pk": event.pk})
    report = preview(client(sm).patch(url + "?price_drop_preview=1", {"payment_amount": "12.00"}, format="json"))
    assert [item["difference"] for item in report["items"]] == ["8.00"]
    assert client(sm).patch(url, {"payment_amount": "12.00"}, format="json").status_code == 200
    case = RefundCase.objects.get()
    assert case.payment_id == payment.pk and case.due_amount == D("8.00")
