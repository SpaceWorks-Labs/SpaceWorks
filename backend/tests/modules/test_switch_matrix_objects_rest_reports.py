"""CX11B: reports resolve the same retained resource on browser/native sessions."""
from datetime import timedelta
from decimal import Decimal
import json
from tests.bookings.pass_helpers import pdf_text
from apps.audit.models import AuditLog

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking
from tests.modules.switch_matrix_object_helpers import client_for, object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, domain_rows, switch
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("report,feature", [
    ("booking-resource-utilization", "bookings.analytics"),
    ("booking-resource-utilization-pdf", "bookings.utilization_pdf"),
    ("booking-reservations", "bookings.exports"), ("booking-answers", "bookings.exports"),
])
@pytest.mark.parametrize("gate", ["reports", "bookings", "feature"])
def test_resource_report_switches_preserve_the_subject_and_its_reservations(native, report, feature, gate):
    space, client, objects = object_world(native)
    other = live_space("cx11b-report-foreign", MODULE_KEYS)
    foreign = client_for(make_staff(other, username="cx11b-report-foreign-manager", access_status="active"), other, native)
    space.timezone = "UTC"
    space.save(update_fields=["timezone"])
    start = (timezone.now() + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    booking = Booking.objects.create(space=objects["room"], name="Retained report borrower", email="report@example.test",
        starts_at=start + timedelta(hours=1), ends_at=start + timedelta(hours=2), status="confirmed", note="Retained report note",
        custom_answers={"purpose": "Retained report answer"})
    pdf = report.endswith("-pdf")
    url = reverse("report-export" if pdf else "analytics-generic", args=[space.pk, report])
    query = {"subject_kind": "bookable_space", "subject_id": objects["room"].pk,
             "start": start.date().isoformat(), "end": start.date().isoformat()}
    if pdf:
        query["format"] = "pdf"
    def assert_seeded_report(response):
        assert response_pair(response) == (200, None), getattr(response, "data", None)
        if pdf:
            assert response["Content-Type"] == "application/pdf"
            text = pdf_text(response.content)
            assert objects["room"].name in text
            assert str(objects["room"].pk) in text
            for figure in ("1.00", "24.00", "4.17"):
                assert figure in text, text
        else:
            records = response.json()["typed_rows"]
            assert len(records) == 1, "An empty report must fail the seeded-subject proof"
            row = records[0]
            assert row["space_id"] == objects["room"].pk
            if report == "booking-resource-utilization":
                assert (row["space_name"], row["booked"], row["upcoming"], row["completed"],
                        row["arrived_reservations"], row["confirmed_without_recorded_arrival"]) == (
                    objects["room"].name, 1, 1, 0, 0, 1)
                assert tuple(Decimal(str(row[k])) for k in (
                    "reserved_hours", "completed_hours", "window_hours", "reservation_utilization_percent")) == (
                        Decimal("1.00"), Decimal("0.00"), Decimal("24.00"), Decimal("4.17"))
            else:
                assert (row["booking_id"], row["status"]) == (booking.pk, "confirmed")
                if report == "booking-reservations":
                    assert (row["name"], row["email"], row["space_name"]) == (
                        "Retained report borrower", "report@example.test", objects["room"].name)
                else:
                    assert json.loads(row["answers"]) == {"purpose": "Retained report answer"}

    audit_ids = set(AuditLog.objects.values_list("pk", flat=True))
    response = client.get(url, query)
    assert_seeded_report(response)
    assert list(AuditLog.objects.exclude(pk__in=audit_ids).values_list("action", flat=True)) == (
        ["report.downloaded"] if pdf else ["report.previewed"])
    with no_domain_writes():
        hidden = foreign.get(url, query)
    assert response_pair(hidden) == ((403, "permission_denied") if native else (404, "not_found")), getattr(hidden, "data", None)
    before = domain_rows()
    key = feature if gate == "feature" else gate
    original = switch(space, key)
    with no_domain_writes():
        response = client.get(url, query)
    assert response_pair(response) == (404, "feature_disabled" if gate == "feature" else "module_disabled"), response.data
    with no_domain_writes():
        hidden = foreign.get(url, query)
    assert response_pair(hidden) == ((403, "permission_denied") if native else (404, "not_found")), getattr(hidden, "data", None)
    assert domain_rows() == before
    switch(space, key, original=original)
    assert domain_rows() == before
    response = client.get(url, query)
    assert_seeded_report(response)
