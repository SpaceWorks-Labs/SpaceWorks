import csv
from dataclasses import replace
from io import BytesIO, StringIO

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from apps.operations import report_registry, report_schedule_services as schedules, reports
from apps.operations.models_report_schedules import ReportSchedule
from apps.operations.report_output import project_report_output
from apps.operations.report_types import ReportDefinition, ReportResult
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space


@pytest.fixture
def leaky_report(monkeypatch):
    definition = ReportDefinition("infra-output", "unused.infra_output", ("period", "count"),
                                  deployment_aggregate=False, allowed_formats=("csv", "xlsx", "pdf"),
                                  pdf_renderer_path="unused.pdf_renderer")
    monkeypatch.setitem(report_registry.REPORT_REGISTRY, definition.key, definition)
    result = ReportResult(("period", "count", "api_key"), [
        {"period": "2026-10-12", "count": 3, "api_key": "private-value", "raw_audit_meta": {"actor": "private"}},
    ], {"source": "live", "grain": "week", "arrival_counts_available": True,
        "delivery_payload": {"private": "value"}})
    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: lambda *_args, **_kwargs: result)
    return definition, result


@pytest.mark.parametrize("kind", ["canonical", "matrix", "summary"])
def test_projection_drops_unknown_fields_and_warns_without_logging_values(kind, caplog):
    definition = ReportDefinition("infra-project", "unused", ("count",), deployment_aggregate=False)
    value = {"count": 2, "password": "NEVER-LOG-THIS"}
    source = {"canonical": ReportResult(("count", "password"), [value], {"message_body": "NEVER-LOG-THIS"}),
              "matrix": [["count", "password"], [2, "NEVER-LOG-THIS"]], "summary": value}[kind]
    result = project_report_output(definition, source)
    if kind == "canonical":
        assert result.field_order == ("count",) and result.records == [{"count": 2}] and result.meta == {}
    else:
        assert result == ({"count": 2} if kind == "summary" else [["count"], [2]])
    assert "report_output_fields_dropped" in caplog.text
    assert "NEVER-LOG-THIS" not in caplog.text


def test_preview_and_export_rows_share_the_allowlist(leaky_report):
    preview = reports.report_data(leaky_report[0].key, 123)
    assert preview["rows"] == [["period", "count"], ["2026-10-12", 3]]
    assert preview["typed_rows"] == [{"period": "2026-10-12", "count": 3}]
    assert preview["meta"] == {"source": "live", "grain": "week", "rollup_through": None,
                               "arrival_counts_available": True}
    assert reports.report_rows(leaky_report[0].key, 123) == preview["rows"]
    assert_report_disclosure_safe(preview)


@pytest.mark.parametrize("kind", ["matrix", "summary"])
def test_legacy_results_also_cross_projection_in_report_data(leaky_report, monkeypatch, kind):
    definition = leaky_report[0]
    if kind == "summary":
        definition = replace(definition, summary=True)
        raw = {"count": 3, "secret": "private-value"}
        expected = {"count": 3}
    else:
        raw = [["count", "secret"], [3, "private-value"]]
        expected = {"rows": [["count"], [3]], "typed_rows": []}
    monkeypatch.setitem(report_registry.REPORT_REGISTRY, definition.key, definition)
    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: lambda *_a, **_k: raw)
    assert reports.report_data(definition.key, 123) == expected


def _decoded_artifact(payload, fmt):
    if fmt == "csv":
        # The provenance line has JSON commas; it is deliberately outside CSV data.
        return list(csv.reader(StringIO(payload.decode().split("\n", 1)[1])))
    book = load_workbook(BytesIO(payload), read_only=True)
    return [list(row) for row in book["Report"].iter_rows(values_only=True)]


@pytest.mark.django_db
@pytest.mark.parametrize("fmt", ["csv", "xlsx", "pdf"])
def test_export_views_pass_only_declared_fields_to_each_renderer(leaky_report, monkeypatch, fmt):
    space = make_space("infra-output-download")
    actor = make_member("infra-output-manager", space)
    captured = []
    if fmt == "pdf":
        def render(rows, **kwargs):
            captured.extend(rows)
            return b"%PDF-1.4\ninfra renderer boundary\n"
        monkeypatch.setattr("django.utils.module_loading.import_string", lambda _path: render)
    response = authenticated_client(actor).get(
        f"/api/v1/admin/makerspace/{space.pk}/reports/{leaky_report[0].key}/export?format={fmt}"
    )
    assert response.status_code == 200, getattr(response, "data", None)
    rows = captured if fmt == "pdf" else _decoded_artifact(response.content, fmt)
    assert rows[0] == ["period", "count"]
    assert rows[1][0] == "2026-10-12" and str(rows[1][1]) == "3"
    assert_report_disclosure_safe(rows)


@pytest.mark.django_db
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_scheduled_artifacts_use_the_same_allowlisted_rows(leaky_report, monkeypatch, fmt):
    space = make_space("infra-output-scheduled")
    actor = make_member("infra-output-scheduler", space)
    schedule = ReportSchedule.objects.create(
        makerspace=space, report_key=leaky_report[0].key, created_by=actor, format=fmt,
        next_run_at=timezone.now(), recipient_emails=["external@example.test"],
    )
    captured = []
    monkeypatch.setattr(schedules, "store_report_object", lambda _key, payload, _fmt: captured.append(payload))
    monkeypatch.setattr(schedules, "signed_download_url", lambda _key: "https://example.test/report")
    monkeypatch.setattr(schedules, "_send", lambda *_args, **_kwargs: [])  # _send(..., delivery=)
    delivery = schedules._build_and_deliver(schedule, leaky_report[0], timezone.now(), actor)
    assert delivery.status == "sent" and len(captured) == 1
    rows = _decoded_artifact(captured[0], fmt)
    assert rows[0] == ["period", "count"]
    assert_report_disclosure_safe(rows)
