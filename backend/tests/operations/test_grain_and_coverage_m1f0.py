from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.operations import org_report_aggregate, org_reports, report_registry, views_org_reports
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.report_coverage_contract import required_report_modules
from apps.operations.report_scope import combined_report_scope
from apps.operations.report_types import ReportResult
from apps.operations.reports_common import period_expression
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space, make_user


def _qr_row(**overrides):
    return dict(period="2026-10-12", context="issue", target_type="product", target_id=7,
                hour_of_week=0, count=2, **overrides)


@pytest.mark.django_db
@pytest.mark.parametrize("timestamp,zone,expected", [
    ("2027-01-01T12:00:00+00:00", "UTC", "2026-12-28"),
    ("2026-10-11T20:00:00+00:00", "Asia/Kolkata", "2026-10-12"),
    ("2026-10-12T01:00:00+00:00", "America/Los_Angeles", "2026-10-05"),
])
def test_week_is_a_real_iso_monday_sql_bucket_in_local_calendar(timestamp, zone, expected):
    actor = make_user("infra-week")
    User.objects.filter(pk=actor.pk).update(date_joined=datetime.fromisoformat(timestamp))
    expression = period_expression("date_joined", "week", makerspace=SimpleNamespace(timezone=zone))
    result = User.objects.filter(pk=actor.pk).annotate(period=expression).values_list("period", flat=True).get()
    assert result.date().isoformat() == expected
    assert result.weekday() == 0 and result.hour == 0


def test_week_accepts_explicit_timezone_and_rejects_invalid_options():
    assert period_expression("created_at", "week", tzinfo=ZoneInfo("UTC")).kind == "week"
    with pytest.raises(ValueError):
        period_expression("created_at", "quarter")
    with pytest.raises(ValueError):
        period_expression("created_at", "week", makerspace=SimpleNamespace(timezone="UTC"),
                          tzinfo=ZoneInfo("UTC"))


@pytest.mark.django_db
def test_organization_view_validates_and_forwards_requested_grain(monkeypatch):
    definition = replace(report_registry.REPORT_REGISTRY["qr-scans"], grains=("day", "week", "month"))
    monkeypatch.setitem(report_registry.REPORT_REGISTRY, definition.key, definition)
    space = make_space("infra-org-grain-view")
    actor = make_member("infra-org-grain-actor", space)
    monkeypatch.setattr(views_org_reports, "_organization_for_report", lambda *_args: object())
    monkeypatch.setattr(views_org_reports, "resolve_organization_report_scope", lambda *_args: object())
    captured = []

    def build(*_args, **kwargs):
        captured.append(kwargs)
        return {"report_key": definition.key, "breakdown": [], "total": {"rows": []}}

    monkeypatch.setattr(org_reports, "organization_report_data", build)
    client = authenticated_client(actor)
    response = client.get("/api/v1/admin/organizations/123/analytics/qr-scans?grain=week")
    assert response.status_code == 200, response.data
    assert captured[0]["grain"] == "week"
    invalid = client.get("/api/v1/admin/organizations/123/analytics/qr-scans?grain=quarter")
    assert invalid.status_code == 400 and len(captured) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("grains", [(), ("day", "week", "month")])
def test_organization_orchestration_forwards_grain_only_to_supporting_builders(monkeypatch, grains):
    definition = replace(report_registry.REPORT_REGISTRY["qr-scans"], grains=grains)
    space = make_space("infra-org-grain-builder")
    scope = combined_report_scope(Makerspace.objects.filter(pk=space.pk))
    captured = []

    def build(makerspace_id, **kwargs):
        captured.append(kwargs)
        row = _qr_row()
        return ReportResult(tuple(row), [row])

    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: build)
    payload = org_reports.organization_report_data(definition, scope, limit=10, grain="week")
    assert captured[0]["limit"] is None
    assert (captured[0].get("grain") == "week") if grains else ("grain" not in captured[0])
    assert payload["total"]["rows"] == [_qr_row()]


def test_registered_combine_receives_all_sources_and_recomputes_weighted_rate(monkeypatch):
    monkeypatch.setattr(org_report_aggregate, "COMBINE_FUNCTIONS", {})

    def combine(rows_by_space, *, limit):
        rows = [row for _, records in rows_by_space for row in records]
        numerator = sum(row["_numerator"] for row in rows)
        denominator = sum(row["_denominator"] for row in rows)
        return [{"rate": numerator / denominator * 100}][:limit]

    assert org_report_aggregate.register_combine("qr-scans", combine) is combine
    rows = [(1, [{"_numerator": 1, "_denominator": 1}]),
            (2, [{"_numerator": 0, "_denominator": 9}])]
    assert org_report_aggregate.aggregate_rows("qr-scans", rows, limit=1) == [{"rate": 10.0}]
    assert org_report_aggregate.register_combine("qr-scans", combine) is combine
    with pytest.raises(ValueError, match="Duplicate"):
        org_report_aggregate.register_combine("qr-scans", lambda *_a: [])
    with pytest.raises(TypeError):
        org_report_aggregate.register_combine("infra-non-callable", None)


@pytest.mark.django_db
def test_organization_keeps_private_denominators_until_combine_then_projects(monkeypatch):
    space = make_space("infra-org-private-input")
    definition = report_registry.REPORT_REGISTRY["qr-scans"]
    scope = combined_report_scope(Makerspace.objects.filter(pk=space.pk))
    source = _qr_row(_denominator=10, raw_audit_meta={"body": "private"})
    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: lambda *_a, **_k:
                        ReportResult(tuple(source), [source]))

    def combine(_key, rows_by_space, *, limit):
        row = rows_by_space[0][1][0]
        assert row["_denominator"] == 10
        return [{**row, "count": row["count"] / row["_denominator"], "password": "private"}]

    monkeypatch.setattr(org_reports, "aggregate_rows", combine)
    response = org_reports.organization_report_data(definition, scope, limit=10)
    assert response["total"]["rows"] == [{**_qr_row(), "count": 0.2}]
    assert response["breakdown"][0]["rows"] == [_qr_row()]
    assert_report_disclosure_safe(response)


# Static debt list: do NOT derive this mark from runtime registration. A builder
# lane removes its key from this set when complete; unexpected completion is a
# strict XPASS and a regression of a completed key is a normal failing test.
_PENDING_KEYS = frozenset({
    "most-lent", "asset-usage", "loan-throughput", "inventory-utilisation", "overdue-loans",
    "damaged-lost", "longest-loans", "request-funnel", "problem-reports", "summary",
    "qr-scans", "inventory-control", "evidence-compliance", "import-quality",
    "stocktake-variance", "stock-transfers", "procurement-performance", "stock-health", "inventory-watch-demand",
    "machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
    "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs", "machine-errors",
    "consumable-usage", "consumable-pools", "warranty-expiry", "booking-occupancy", "booking-lead-time",
    "booking-top-members", "event-signups", "event-revenue", "event-funnel", "event-checkin-times",
    "event-feedback-scores", "membership-growth", "member-retention", "membership-revenue",
    "revenue-over-time", "payments-ageing", "cash-book", "mobile-devices", "mobile-auth", "device-health",
    "presence-activity", "audit-activity", "organization-membership", "platform-services", "platform-usage",
})
_COMPLETE_KEYS = {"booking-utilization", "payment-reconciliation", "communications-health", "module-operational-health"}

_AB_COMPLETED_KEYS = frozenset({
    "most-lent", "asset-usage", "loan-throughput", "inventory-utilisation", "overdue-loans",
    "damaged-lost", "longest-loans", "request-funnel", "problem-reports", "summary",
    "qr-scans", "inventory-control", "stocktake-variance", "stock-transfers",
    "procurement-performance", "stock-health", "inventory-watch-demand", "consumable-usage", "consumable-pools",
})
_PENDING_KEYS = _PENDING_KEYS - _AB_COMPLETED_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _AB_COMPLETED_KEYS
_PENDING_KEYS = _PENDING_KEYS - {"mobile-devices", "mobile-auth"}
_COMPLETE_KEYS = _COMPLETE_KEYS | {"mobile-devices", "mobile-auth"}

_MACHINE_COMPLETE_KEYS = {
    "machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
    "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs", "machine-errors", "warranty-expiry",
}
_PENDING_KEYS = _PENDING_KEYS - _MACHINE_COMPLETE_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _MACHINE_COMPLETE_KEYS
_DE_COMPLETE_KEYS = {"booking-occupancy", "booking-lead-time", "booking-top-members", "event-signups", "event-revenue",
                     "event-funnel", "event-checkin-times", "event-feedback-scores"}
_PENDING_KEYS -= _DE_COMPLETE_KEYS
_COMPLETE_KEYS |= _DE_COMPLETE_KEYS
_FG_COMPLETE_KEYS = {"membership-growth", "member-retention", "membership-revenue", "revenue-over-time", "payments-ageing", "payment-reconciliation", "cash-book"}
_PENDING_KEYS = _PENDING_KEYS - _FG_COMPLETE_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _FG_COMPLETE_KEYS
_J_COMPLETE_KEYS = {"device-health", "presence-activity", "audit-activity", "organization-membership", "platform-services", "platform-usage"}
_PENDING_KEYS = _PENDING_KEYS - _J_COMPLETE_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _J_COMPLETE_KEYS

_CHART_COMPLETE_KEYS = {"evidence-compliance", "import-quality"}
_PENDING_KEYS = _PENDING_KEYS - _CHART_COMPLETE_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _CHART_COMPLETE_KEYS
# Addressed SMS/WhatsApp associations reuse these completed report keys.
_MESSAGING_COMPLETE_KEYS = {"communications-health", "platform-services"}
_PENDING_KEYS = _PENDING_KEYS - _MESSAGING_COMPLETE_KEYS
_COMPLETE_KEYS = _COMPLETE_KEYS | _MESSAGING_COMPLETE_KEYS


def test_coverage_contract_has_an_explicit_acceptance_state_for_every_key():
    assert set(required_report_modules()) == _PENDING_KEYS | _COMPLETE_KEYS


@pytest.mark.parametrize("report_key,required_modules", [
    pytest.param(key, modules, id=key, marks=pytest.mark.xfail(
        strict=True, reason="Phase 1f builder/module association pending; remove mark when delivered",
    ) if key in _PENDING_KEYS else ())
    for key, modules in sorted(required_report_modules().items())
])
def test_phase_1f_report_coverage_acceptance(report_key, required_modules):
    definition = report_registry.REPORT_REGISTRY.get(report_key)
    assert definition is not None, f"Missing report {report_key}"
    modules = set(definition.required_modules) | set(definition.section_modules)
    modules.update(module for module, coverage in REPORT_MODULE_COVERAGE.items() if report_key in coverage.reports)
    assert required_modules <= modules, f"{report_key} missing module associations: {required_modules - modules}"
