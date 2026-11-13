"""L6 G31: a series pass registers the buyer for every future occurrence; a cancelled
occurrence opens the organiser's partial amount as a staff-approved due (no money moved)."""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events import services, services_series
from apps.events.models import EventOrder, EventPassType, EventSeries
from apps.events.services_series_lifecycle import publish_series
from apps.payments.models import Payment, Refund, RefundCase
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff, settle_offline, verified

pytestmark = pytest.mark.django_db


def _series(space, staff):
    series, occurrences = services_series.create_series(
        makerspace=space, actor=staff, title="Weekly club", description="", location="",
        registration_audience="accounts", recurrence_timezone="UTC",
        dtstart_local_date=(timezone.now() + timedelta(days=1)).date(), dtstart_local_time=time(10),
        recurrence_rule="FREQ=DAILY;COUNT=3", duration_minutes=60,
        is_public=True,  # occurrences copy the series' visibility when they are materialized
    )
    publish_series(series, actor=staff)
    return series


def test_pass_covers_occurrences_and_cancel_opens_partial_due(django_capture_on_commit_callbacks):
    space = l6_space()
    staff = make_staff(space)
    series = _series(space, staff)
    pass_type = EventPassType.objects.create(makerspace=space, series=series, name="Season", amount=Decimal(30),
                                             occurrence_refund_amount=Decimal(8))
    buyer = verified("buyer")
    url = reverse("member-series-passes", kwargs={"makerspace_id": space.pk, "series_id": series.pk})
    assert client_for(buyer).get(url).data[0]["name"] == "Season"
    response = client_for(buyer).post(url, {"pass_type_id": pass_type.pk}, format="json")
    assert response.status_code == 201, response.data
    order = EventOrder.objects.get()
    payment = Payment.objects.get(subject_type="event_order", subject_id=order.pk)
    assert payment.amount == Decimal("30.00") and order.seats.count() == 3
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(payment, staff)
    assert buyer.event_registrations.filter(status="registered").count() == 3
    first = series.occurrences.order_by("starts_at").first()
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(first, actor=staff)
    case = RefundCase.objects.get(payment=payment)
    assert case.due_amount == Decimal("8.00") and case.status == "open"
    assert not Refund.objects.exists()
    assert order.dues.get().kind == "occurrence_cancelled"


def test_passes_switch_off_is_refused():
    space = l6_space(features=["events.orders"])
    staff = make_staff(space)
    series = _series(space, staff)
    url = reverse("member-series-passes", kwargs={"makerspace_id": space.pk, "series_id": series.pk})
    assert client_for(verified("buyer")).get(url).status_code == 404  # off switch: no surface (#95)
