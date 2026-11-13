"""Local probe (untracked): why a series-pass buyer seat is deferred."""
import traceback
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.events import orders_claims
from apps.events.models import EventOrder, EventPassType
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff, settle_offline, verified
from tests.events.test_series_passes import _series

pytestmark = pytest.mark.django_db


def test_probe(django_capture_on_commit_callbacks, monkeypatch):
    real, seen = orders_claims.fill_seat, []

    def wrapped(*args, **kwargs):
        try:
            return real(*args, **kwargs)
        except Exception:
            seen.append(traceback.format_exc())
            raise
    monkeypatch.setattr(orders_claims, "fill_seat", wrapped)
    space = l6_space()
    staff = make_staff(space)
    series = _series(space, staff)
    pass_type = EventPassType.objects.create(makerspace=space, series=series, name="Season", amount=Decimal(30),
                                             occurrence_refund_amount=Decimal(8))
    buyer = verified("buyer")
    url = reverse("member-series-passes", kwargs={"makerspace_id": space.pk, "series_id": series.pk})
    assert client_for(buyer).post(url, {"pass_type_id": pass_type.pk}, format="json").status_code == 201
    order = EventOrder.objects.get()
    payment = Payment.objects.get(subject_type="event_order", subject_id=order.pk)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(payment, staff)
    print("PROBE-TRACEBACKS", len(seen))
    for item in seen[:1]:
        print(item[-4000:])
    assert not seen
