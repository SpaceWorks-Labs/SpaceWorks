"""Payment subject types remain usable on deployment aggregate report paths."""

import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.events.services_registration import register
from apps.operations import reports
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import event_space, open_event
from tests.operations.test_finance_reports import cash_payment
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", ["revenue-over-time", "cash-book"])
def test_payment_subject_type_allows_filtered_aggregate_preview_and_export(key):
    actor = User.objects.create_superuser(username="aggregate-review", email="aggregate@example.test", password="test")
    space = event_space("aggregate-payment-filter")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports"})
    space.save(update_fields=["enabled_modules"])
    event = open_event(space, payment_amount="12.00")
    member = User.objects.create_user("aggregate-member", email="member@example.test", access_status="active")
    registration = register(event, member=member, actor=member, phone="12345678")
    payment = Payment.objects.get(makerspace=space, subject_type="event_registration", subject_id=registration.pk)
    mark_offline(payment, actor, settlement_details())
    cash_payment(space, actor, amount="99.00")
    client = client_for(actor)
    params = {"subject_type": "event_registration"}
    preview = client.get(reverse("analytics-aggregate", args=[key]), params)
    assert preview.status_code == 200, preview.data
    rows = preview.data["typed_rows"]
    assert len(rows) == 1 and str(rows[0]["collected_amount"]) == "12.00"
    export = client.get(reverse("report-export-aggregate", args=[key]), {**params, "format": "csv"})
    assert export.status_code == 200
    content = b"".join(export.streaming_content) if export.streaming else export.content
    assert b"12.00" in content and b"99.00" not in content


@pytest.mark.parametrize("filters", [{"subject_kind": "event"}, {"subject_id": 1},
                                     {"subject_kind": "event", "subject_id": 1}])
@pytest.mark.parametrize("build", [reports.report_data, reports.report_rows])
def test_new_subject_keys_still_refuse_aggregate_reports(build, filters):
    with pytest.raises(PermissionDenied, match="tenant-local"):
        build("revenue-over-time", report_filters=filters)
