from copy import deepcopy
import pytest

from apps.operations import org_report_scope, org_reports, report_registry, reports
from apps.operations.report_schedule_services import _skip_reason
from apps.operations.report_types import ReportDefinition, ReportNotFound
from apps.operations.report_validation import (
    check_report_definitions, validate_chart_spec, validate_report_definition,
)
from tests.operations.report_assertions import assert_report_disclosure_safe


def _definition(**kwargs):
    return ReportDefinition("infra-contract", "unused.builder", ("period", "count", "currency"), **kwargs)


def _spec():
    return {"series": ["currency"], "x": {"field": "period", "kind": "time"},
            "values": [{"field": "count", "unit": "loans"}], "currency_field": "currency",
            "partition": "currency", "negatives": "clip",
            "truncation": {"top_n": 10, "other_label": "Other"},
            "alt_template": "{count} loans in {period}"}


def test_definition_defaults_are_counts_only_and_chart_optional():
    definition = _definition()
    assert not definition.platform_only and not definition.identity_bearing
    assert definition.chart_spec is None
    validate_report_definition(definition)


@pytest.mark.parametrize("aggregate,schedulable", [(True, False), (False, True), (True, True)])
def test_identity_reports_reject_aggregate_or_schedule(aggregate, schedulable, monkeypatch):
    monkeypatch.setattr(org_report_scope, "EXCLUDED_ORGANIZATION_REPORT_KEYS", {"infra-contract"})
    with pytest.raises(ValueError, match="tenant-only"):
        validate_report_definition(_definition(identity_bearing=True, deployment_aggregate=aggregate,
                                              schedulable=schedulable))


def test_identity_reports_need_explicit_organization_exclusion(monkeypatch):
    definition = _definition(identity_bearing=True, deployment_aggregate=False, schedulable=False)
    with pytest.raises(ValueError, match="organization exclusion"):
        validate_report_definition(definition)
    monkeypatch.setattr(org_report_scope, "EXCLUDED_ORGANIZATION_REPORT_KEYS", {definition.key})
    validate_report_definition(definition)


@pytest.mark.parametrize("aggregate,schedulable", [(False, False), (True, True), (False, True)])
def test_platform_reports_require_deployment_and_no_schedule(aggregate, schedulable):
    with pytest.raises(ValueError, match="Platform-only"):
        validate_report_definition(_definition(platform_only=True, deployment_aggregate=aggregate,
                                              schedulable=schedulable))


def test_registry_validates_and_system_check_reports_same_invalid_definition(monkeypatch):
    definition = _definition(identity_bearing=True)
    monkeypatch.setitem(report_registry.REPORT_REGISTRY, definition.key, definition)
    with pytest.raises(ValueError):
        report_registry.report_definition(definition.key)
    errors = check_report_definitions()
    assert any(error.id == "operations.E005" and definition.key in error.msg for error in errors)


@pytest.mark.parametrize("key", ["event-equipment", "booking-equipment"])
def test_equipment_subject_report_is_valid_and_excluded_from_organization_scope(key):
    from apps.organizations.models import Organization

    definition = report_registry.report_definition(key)
    assert definition.identity_bearing and not definition.schedulable
    assert not definition.deployment_aggregate
    assert not any(error.id == "operations.E005" and key in error.msg
                   for error in check_report_definitions())
    with pytest.raises(org_report_scope.UnsupportedOrganizationReport, match="tenant-only"):
        org_report_scope.resolve_organization_report_scope(None, Organization(pk=1), definition)


def test_chart_spec_validates_f1_complete_contract():
    validate_chart_spec(_spec(), _definition().fields)
    spec = _spec()
    spec.update(series=[], currency_field=None, partition=None, truncation=None, negatives="allow")
    spec["x"]["kind"] = "category"
    validate_chart_spec(spec, _definition().fields)


@pytest.mark.parametrize("key,value", [
    ("series", ["missing"]), ("series", ["currency", "currency"]),
    ("x", {"field": "period", "kind": "week"}),
    ("values", [{"field": "missing", "unit": "count"}]),
    ("values", [{"field": "count", "unit": ""}]),
    ("currency_field", "missing"), ("partition", "person"), ("negatives", "absolute"),
    ("truncation", {"top_n": True, "other_label": "Other"}),
    ("truncation", {"top_n": 0, "other_label": "Other"}),
    ("alt_template", "{count.__class__}"), ("alt_template", "{missing}"),
])
def test_chart_spec_rejects_invalid_shapes_and_undeclared_fields(key, value):
    spec = deepcopy(_spec())
    spec[key] = value
    with pytest.raises(ValueError):
        validate_chart_spec(spec, _definition().fields)


def test_chart_spec_rejects_extra_missing_and_unbound_partition():
    for change in (lambda s: s.pop("series"), lambda s: s.update(extra="ignored"),
                   lambda s: s.update(currency_field=None), lambda s: s.update(partition="tenant")):
        spec = _spec()
        change(spec)
        with pytest.raises(ValueError):
            validate_chart_spec(spec, _definition().fields)


@pytest.mark.parametrize("bad", [
    {"secret": "x"}, {"nested": [{"value": "api_key=credential"}]},
    {"private_key": "x"}, {"webhook_url": "https://example.test"}, {"value": "smtp://user@host"},
    {"raw_audit_meta": {}}, {"delivery_payload": {}}, {"message_body": "hello"},
    {"feedback_answers": ["hello"]}, {"meta": {"payload": {}}},
    [["message_body"], ["private message"]], [["raw_audit_meta"], ["private audit"]],
    {"rows": [["answers"], ["private answer"]]}, {"answers": ["private answer"]},
])
def test_reusable_credential_guard_rejects_nested_secrets_and_raw_content(bad):
    with pytest.raises(AssertionError):
        assert_report_disclosure_safe(bad)


def test_reusable_guard_accepts_counts_and_provenance():
    assert_report_disclosure_safe({"typed_rows": [{"period": "2026-10-12", "count": 4}],
                                   "meta": {"source": "live", "grain": "week"}})


def test_reusable_guard_allows_tenant_subject_feedback_only_when_explicit():
    assert_report_disclosure_safe([["answers"], ["attendee feedback"]], aggregate=False)


@pytest.mark.parametrize("report_key", ["top-borrowers", "active-loans", "returns"])
def test_shipped_identity_reports_are_tenant_only_unschedulable_and_org_excluded(report_key):
    from types import SimpleNamespace

    definition = report_registry.report_definition(report_key)
    assert definition.identity_bearing
    assert not definition.deployment_aggregate and not definition.schedulable
    assert report_key in org_report_scope.EXCLUDED_ORGANIZATION_REPORT_KEYS
    assert report_key not in org_reports.organization_strategy_keys()
    assert report_key not in report_registry.DEPLOYMENT_AGGREGATE_REPORT_KEYS
    with pytest.raises(ReportNotFound):
        report_registry.report_definition(report_key, deployment_aggregate=True)
    for runner in (reports.report_data, reports.report_rows):
        with pytest.raises(ReportNotFound):
            runner(report_key)
    assert _skip_reason(SimpleNamespace(filters={}), definition) == "report_unavailable"
