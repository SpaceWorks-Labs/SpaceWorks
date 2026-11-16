import csv
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
import json

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.operations import reports
from apps.operations.models_saved_views import SavedView
from apps.operations.reports_booking_exports import build_answers, build_reservations
from tests.encryption.conftest import enabled_encryption
from tests.operations.booking_report_helpers import KEYS, auditor, booking, client_for, filters, fixture, period

pytestmark = pytest.mark.django_db


def test_saved_report_replay_revocation_and_owner_authority():
    tenant, manager, grantee, resource, grant, _ = fixture()
    auditor(tenant, grantee)
    client = client_for(grantee)
    base = reverse("saved-report-views", args=[tenant.pk])
    payload = {"name": "Resource report", "state": {"report_key": "booking-reservations",
        "filters": period(resource), "grain": "day", "columns": ["name", "status"]}}
    created = client.post(base, payload, format="json")
    assert created.status_code == 201, created.data
    pk = created.data["id"]
    url = reverse("saved-report-view-detail", args=[tenant.pk, pk])
    assert client.get(url).data["state"] == payload["state"]
    replay = client.get(reverse("analytics-generic", args=[tenant.pk, "booking-reservations"]), created.data["state"]["filters"])
    assert replay.status_code == 200
    # A shared preference conveys no authority. Recheck its owner as well as reader.
    SavedView.objects.filter(pk=pk).update(shared=True)
    assert client_for(manager).get(url).status_code == 200
    grant.revoked_at = timezone.now(); grant.save(update_fields=["revoked_at"])
    assert client.get(url).status_code == 403
    assert client.get(base).data["results"] == []
    assert client_for(manager).get(url).status_code == 403
    assert client_for(manager).get(base).data["results"] == []
    assert AuditLog.objects.filter(makerspace=tenant, action="saved_view.created", target_id=str(pk)).exists()


def test_tenant_local_half_open_window_provenance_and_formula_safe_columns():
    tenant, actor, _, resource, *_ = fixture()
    # Oct 1 in Kolkata starts Sep 30 at 18:30 UTC, and ends Oct 1 at 18:30 UTC.
    start = datetime(2026, 9, 30, 18, 30, tzinfo=dt_timezone.utc)
    end = start + timedelta(days=1)
    included = booking(resource, starts_at=start - timedelta(hours=2), ends_at=start + timedelta(hours=1),
        custom_answers={"answers": [{"id": "q", "label": "Historical label", "value": "=1+1"}]})
    included.name = "=HYPERLINK(1)"; included.email = "+formula@example.test"; included.phone = "@formula"
    included.note = "Private note must not export"; included.save()
    booking(resource, starts_at=start - timedelta(hours=1), ends_at=start)
    booking(resource, starts_at=end, ends_at=end + timedelta(hours=1))
    client = client_for(actor)
    request_filters = {**filters(resource), "start": "2026-10-01", "end": "2026-10-01"}
    for key in ("booking-reservations", "booking-answers"):
        response = client.get(reverse("report-export", args=[tenant.pk, key]), request_filters)
        assert response.status_code == 200, getattr(response, "data", None)
        assert response["Cache-Control"] == "private, no-store"
        content = response.content.decode()
        provenance, data = content.split("\r\n", 1)
        assert 'subject_kind' in provenance and 'bookable_space' in provenance and 'subject_id' in provenance
        assert '2026-09-30T18:30:00+00:00' in provenance
        assert '2026-10-01T18:30:00+00:00' in provenance
        records = list(csv.DictReader(StringIO(data)))
        assert [int(row["booking_id"]) for row in records] == [included.pk]
        assert str(included.public_token) not in content
        assert not {"public_token", "checkin_token", "note", "member_id", "payment"}.intersection(records[0])
        assert included.note not in content
        if key == "booking-reservations":
            assert records[0]["name"].startswith("'=") and records[0]["email"].startswith("'+") and records[0]["phone"].startswith("'@")
        else:
            assert json.loads(records[0]["answers"]) == included.custom_answers
    assert AuditLog.objects.filter(makerspace=tenant, action="report.downloaded").count() == 2
    preview = client.get(reverse("analytics-generic", args=[tenant.pk, "booking-answers"]), request_filters)
    assert preview.status_code == 200 and preview["Cache-Control"] == "private, no-store"
    assert AuditLog.objects.filter(makerspace=tenant, action="report.previewed").exists()


@pytest.mark.parametrize("builder", [build_reservations, build_answers])
def test_encrypted_accessors_and_eager_tenant_path(builder, monkeypatch):
    with enabled_encryption():
        tenant, _, _, resource, *_ = fixture()
        expected = [booking(resource, custom_answers={"answer": f"Café {index}"}) for index in range(4)]
        from apps.encryption.crypto import is_envelope
        assert is_envelope(Booking.objects.filter(pk=expected[0].pk).values_list("name", flat=True).get())
        read_answers = []
        getattribute = Booking.__getattribute__
        def accessor(instance, key):
            if key == "custom_answers":
                read_answers.append(instance.pk)
            return getattribute(instance, key)
        monkeypatch.setattr(Booking, "__getattribute__", accessor)
        with override_settings(PII_ENCRYPTION_DUAL_READ=False), CaptureQueriesContext(connection) as queries:
            result = builder(tenant.pk, **filters(resource))
        assert len(result.records) == 4
        if builder == build_reservations:
            assert {row["name"] for row in result.records} == {"Booker Café α"}
            assert {row["email"] for row in result.records} == {"booker@example.test"}
        else:
            assert set(read_answers) == {row.pk for row in expected}
            assert json.loads(result.records[0]["answers"]) == {"answer": "Café 0"}
        domain_reads = [q for q in queries if 'FROM "bookings_' in q["sql"]]
        # One read for the rows; build_reservations adds one batched organization-link read for the
        # organization column (decision 218), constant in the row count, never one per booking.
        assert len(domain_reads) == (2 if builder == build_reservations else 1)
        foreign, *_ = fixture("foreign-encrypted-booking-report")
        assert not builder(foreign.pk, **filters(resource)).records


def test_pdf_is_audited_bounded_and_contains_builder_numbers_and_unicode():
    import base64
    import re
    import zlib
    tenant, actor, _, resource, *_ = fixture()
    resource.name = "Café α " + "Long resource description " * 5
    resource.save(update_fields=["name"])
    start = datetime(2026, 10, 1, tzinfo=dt_timezone.utc)
    booking(resource, starts_at=start, ends_at=start + timedelta(hours=4), status="completed")
    response = client_for(actor).get(reverse("report-export", args=[tenant.pk, "booking-resource-utilization-pdf"]),
        {**filters(resource), "start": "2026-10-01", "end": "2026-10-01", "format": "pdf"})
    assert response.status_code == 200, getattr(response, "data", None)
    assert response.content.startswith(b"%PDF-") and response["Cache-Control"] == "private, no-store"
    assert AuditLog.objects.filter(makerspace=tenant, action="report.downloaded", meta__format="pdf").exists()
    streams = []
    for chunk in re.findall(rb"stream\r?\n(.*?)endstream", response.content, re.S):
        try:
            chunk = base64.a85decode(chunk.strip(), adobe=True) if chunk.rstrip().endswith(b"~>") else chunk.strip()
            streams.append(zlib.decompress(chunk))
        except (ValueError, zlib.error):
            streams.append(chunk)
    text = b"\n".join(streams)
    assert b"4.00" in text and b"subject_id" in text and b"calendar reservation occupancy" in text
    assert b"<00E9>" in text.upper() and b"<03B1>" in text.upper()
    assert b"Private note" not in text and b"checkin" not in text


def test_catalog_hides_subject_only_reports_and_invalid_dates_cannot_render():
    tenant, actor, _, resource, *_ = fixture()
    client = client_for(actor)
    entries = client.get(reverse("report-catalog", args=[tenant.pk])).data["results"]
    assert not set(KEYS) & {row["key"] for row in entries}
    assert "booking-utilization" in {row["key"] for row in entries}
    url = reverse("report-export", args=[tenant.pk, "booking-resource-utilization-pdf"])
    for dates in ({}, {"start": "2026-10-01"}, {"end": "2026-10-01"},
                  {"start": "bad", "end": "2026-10-01"}, {"start": "2026-10-02", "end": "2026-10-01"}):
        assert client.get(url, {**filters(resource), **dates, "format": "pdf"}).status_code == 400


@pytest.mark.parametrize("day, hours", [("2026-03-08", "23.00"), ("2026-11-01", "25.00")])
def test_tenant_calendar_utilization_uses_real_dst_window_hours(day, hours):
    tenant, actor, _, resource, *_ = fixture()
    tenant.timezone = "America/New_York"; tenant.save(update_fields=["timezone"])
    result = client_for(actor).get(reverse("analytics-generic", args=[tenant.pk, "booking-resource-utilization"]),
        {**filters(resource), "start": day, "end": day})
    assert result.status_code == 200, result.data
    row = result.data["typed_rows"][0]
    assert row["window_hours"] == hours
    assert row["reserved_hours"] == "0.00" and row["reservation_utilization_percent"] == 0.0
