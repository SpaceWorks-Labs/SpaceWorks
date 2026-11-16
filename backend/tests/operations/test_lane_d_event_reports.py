from tests.events.manual_grant_fixture import create_manual_grant
from datetime import timedelta
import base64
import re
import zlib
import json
from types import SimpleNamespace
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.events.models import EventFeedbackSurvey, EventFeedbackResponse, EventStaffGrant
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.operations import reports
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_subjects import SubjectFilterSerializer
from apps.operations.serializers_report_schedules import ReportScheduleSerializer
from apps.operations.views_report_views import authorize_view
from apps.operations.report_schedule_services import _skip_reason
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture
from tests.events.ticketing_helpers import account, event_space, open_event

from tests.account_split_g2_helpers import grant_organization_action
from apps.accounts.rbac import Action

pytestmark = pytest.mark.django_db


def filters(event):
    return {"subject_kind": "event", "subject_id": event.pk}


def test_unscoped_catalog_excludes_subject_only_reports_but_event_routes_work(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    client = client_for(actor)
    response = client.get(reverse("report-catalog", args=[space.pk]))
    assert response.status_code == 200
    entries = {row["key"]: row for row in response.data["results"]}
    assert entries["event-attendance"]["available"] is True
    assert not {"event-registrations", "event-feedback", "event-attendance-pdf"} & entries.keys()
    assert all(not REPORT_REGISTRY[key].subject_kind for key in entries)
    # The event drawer still has an exact subject and can preview/download detail.
    for key in ("event-registrations", "event-feedback"):
        preview = client.get(reverse("analytics-generic", args=[space.pk, key]), filters(event))
        assert preview.status_code == 200, preview.data
        download = client.get(reverse("report-export", args=[space.pk, key]), filters(event))
        assert download.status_code == 200
    event.starts_at = timezone.now() - timedelta(hours=3)
    event.ends_at = timezone.now() - timedelta(hours=1)
    event.save()
    pdf = client.get(reverse("report-export", args=[space.pk, "event-attendance-pdf"]),
                     {**filters(event), "format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


def test_one_event_builder_parity_and_no_credentials(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    unrelated = open_event(space); unrelated.title = "Unrelated"; unrelated.save()
    data = reports.report_data("event-attendance", space.pk, actor=actor, report_filters=filters(event))
    assert len(data["typed_rows"]) == 1 and data["typed_rows"][0]["registrations"] == 1
    response = client_for(actor).get(reverse("report-export", args=[space.pk, "event-registrations"]), filters(event))
    assert response.status_code == 200
    text = response.content.decode()
    assert "subject_kind" in text and "subject_id" in text and user.email in text
    assert "checkin_token" not in text and str(registration.checkin_token) not in text
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="report.downloaded").exists()


def test_d6_conjunction_preview_download_saved_view_and_cross_tenant(monkeypatch):
    space, manager, user, event, registration = fixture(monkeypatch)
    grantee = account("report-grantee")
    grant = create_manual_grant(makerspace=space, event=event, user=grantee,
                                         granted_by=manager, permissions=["manage_registrations"])
    state = {"report_key": "event-registrations", "filters": filters(event)}
    # Decision 248 / EB1: a live per-event grant opens that event's reports without tenant VIEW_AUDIT;
    # a person with no grant is still refused.
    stranger = account("report-stranger")
    with pytest.raises(PermissionDenied):
        authorize_view(stranger, space, state)
    assert reports.report_data("event-registrations", space.pk, actor=grantee, report_filters=filters(event))["typed_rows"]
    assert authorize_view(grantee, space, state).key == "event-registrations"
    foreign = open_event(event_space("foreign-report"))
    response = client_for(grantee).get(reverse("analytics-event-attendance", args=[space.pk]), filters(foreign))
    assert response.status_code == 404
    grant.revoked_at = timezone.now(); grant.save()
    with pytest.raises(PermissionDenied):
        reports.report_data("event-registrations", space.pk, actor=grantee, report_filters=filters(event))
    with pytest.raises(PermissionDenied):
        authorize_view(grantee, space, state)


@pytest.mark.parametrize("payload", [{"subject_id": 1}, {"subject_kind": "event"}, {"subject_kind": "event", "subject_id": 0}, {"subject_kind": "unknown", "subject_id": 1}])
def test_subject_pair_boundary(payload):
    serializer = SubjectFilterSerializer(data=payload)
    assert not serializer.is_valid()


def test_all_aggregate_and_schedule_paths_refuse_subjects(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    with pytest.raises(PermissionDenied):
        reports.report_data("event-attendance", actor=actor, report_filters=filters(event))
    for key in ("event-registrations", "event-feedback", "event-attendance-pdf"):
        definition = REPORT_REGISTRY[key]
        assert not definition.schedulable and not definition.deployment_aggregate
        from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
    serializer = ReportScheduleSerializer(data={"report_key": "event-attendance", "filters": filters(event),
        "recipient_emails": ["external@example.test"]}, context={"makerspace": space, "request": SimpleNamespace(user=actor)})
    assert not serializer.is_valid()
    assert _skip_reason(SimpleNamespace(filters=filters(event)), REPORT_REGISTRY["event-attendance"]) == "subject_filter_not_schedulable"


def test_feedback_accessor_and_formula_safe_export(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=[{"id": "q", "label": "Feedback", "type": "short_text", "options": [], "required": False}])
    response = EventFeedbackResponse.objects.create(survey=survey, answers_snapshot=json.dumps({"answers": [{"id": "q", "value": "=HYPERLINK(1)"}]}))
    result = reports.report_data("event-feedback", space.pk, actor=actor, report_filters=filters(event))
    assert result["typed_rows"][0]["response_id"] == response.pk
    assert "HYPERLINK" in result["typed_rows"][0]["answers"]
    from apps.operations.report_exports import _export_cell
    assert _export_cell("=HYPERLINK(1)").startswith("'")


def test_pdf_ends_gate_full_authority_and_builder_numbers(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    with pytest.raises(ValidationError):
        reports.report_rows("event-attendance-pdf", space.pk, actor=actor, report_filters=filters(event))
    event.starts_at = timezone.now() - timedelta(hours=3)
    event.ends_at = timezone.now() - timedelta(hours=1); event.save()
    rows = reports.report_rows("event-attendance-pdf", space.pk, actor=actor, report_filters=filters(event))
    assert rows[1][rows[0].index("registrations")] == 1
    grantee = account("pdf-grantee")
    create_manual_grant(makerspace=space, event=event, user=grantee, granted_by=actor, permissions=["manage_registrations"])
    # Delegated helpers stay members; organization authority supplies tenant VIEW_AUDIT.
    grant_organization_action(space, grantee, Action.VIEW_AUDIT)
    with pytest.raises(PermissionDenied):
        reports.report_rows("event-attendance-pdf", space.pk, actor=grantee, report_filters=filters(event))


def test_pdf_layout_unicode_and_provenance():
    from apps.operations.report_exports_provenance import build_provenance
    from apps.operations.report_pdf import render_pdf
    provenance = build_provenance("event-attendance-pdf", version=1, makerspace_id=1, generated_by="staff", filters={"subject_kind": "event", "subject_id": 2})
    pdf = render_pdf([["title", "registrations"], ["Café α - " + "Long workshop title " * 12, 42]], provenance=provenance, title="Post-event analytics")
    assert pdf.startswith(b"%PDF-")
    streams = []
    for chunk in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            chunk = base64.a85decode(chunk, adobe=True) if chunk.rstrip().endswith(b"~>") else chunk
            streams.append(zlib.decompress(chunk))
        except (ValueError, zlib.error):
            streams.append(chunk)
    # This short fixture uses one embedded font subset. Decode its drawn text
    # through ToUnicode: a map entry alone does not prove a glyph was used.
    cmaps = [stream for stream in streams if b"begincmap" in stream]
    assert len(cmaps) == 1
    characters = {
        int(code, 16): bytes.fromhex(value.decode()).decode("utf-16-be")
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", cmaps[0], re.S)
        for code, value in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block)
    }
    drawn = []
    for stream in streams:
        for literal in re.findall(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", stream):
            raw = re.sub(
                rb"\\([0-7]{1,3}|[\\()])",
                lambda match: bytes([int(match[1], 8)]) if match[1].isdigit() else match[1],
                literal,
            )
            drawn.append("".join(characters[code] for code in raw))
    text = " ".join(drawn)
    assert "Café α - Long workshop title" in text
    assert "42" in text and '"subject_id":2' in text and "Page 1" in text
    # A valid Unicode mapping must also point at a real font glyph, not .notdef.
    from reportlab.pdfbase import pdfmetrics
    from apps.operations.report_pdf_fonts import report_font_name
    face = pdfmetrics.getFont(report_font_name()).face
    assert all(face.charToGlyph.get(ord(char), 0) != 0 for char in "éα")
