"""Every previewable registry entry supplies a chart over its declared output."""

from string import Formatter

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from apps.operations import reports
from apps.operations.platform_scope import require_platform_context
from apps.operations.report_coverage_contract import required_report_modules
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_types import ReportResult
from apps.operations.report_validation import validate_chart_spec
from apps.operations.serializers_report_chart import ReportChartSpecSerializer
from apps.operations.serializers_report_catalog import PlatformAnalyticsReportSerializer
from tests.return_helpers import authenticated_client, make_member, make_space, make_user


@pytest.mark.parametrize("definition", [
    pytest.param(d, id=d.key) for d in REPORT_REGISTRY.values() if d.previewable
])
def test_every_previewable_report_has_a_valid_chart_over_declared_fields(definition):
    spec = definition.chart_spec
    assert spec is not None, f"{definition.key} has no chart_spec"
    validate_chart_spec(spec, definition.fields)
    referenced = {spec["x"]["field"], *(v["field"] for v in spec["values"]), *spec["series"]}
    if spec["currency_field"] is not None:
        referenced.add(spec["currency_field"])
    referenced.update(name for _, name, _, _ in Formatter().parse(spec["alt_template"])
                      if name is not None and name != "count")
    assert referenced <= set(definition.fields)


@pytest.mark.parametrize("key", ["payment-cash-book", "payments-ledger", "accounting-journal"])
def test_remaining_money_charts_partition_currency_and_preserve_negatives(key):
    spec = REPORT_REGISTRY[key].chart_spec
    assert spec["currency_field"] == "currency"
    assert spec["partition"] == "currency"
    assert spec["negatives"] == "allow"
    assert all(value["unit"] == "currency_major" for value in spec["values"])


def test_evidence_and_import_coverage_are_independent():
    modules = required_report_modules()
    assert modules["evidence-compliance"] == {"evidence_uploads"}
    assert modules["import-quality"] == {"bulk_import"}


@pytest.mark.parametrize("key", ["booking-reservations", "booking-answers", "event-registrations", "event-feedback", "audit-trail"])
def test_detail_tables_preserve_export_allowlists_without_count_columns(key):
    definition = REPORT_REGISTRY[key]
    assert "count" not in definition.fields
    assert definition.version == 1
    assert definition.chart_hint == "table"
    assert definition.chart_spec["values"] == []
    validate_chart_spec(definition.chart_spec, definition.fields)
    serializer = ReportChartSpecSerializer(data=definition.chart_spec)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("override", [{"series": ["id"]}, {"partition": "tenant"},
                                      {"x": {"field": "id", "kind": "time"}}])
def test_table_specs_refuse_aggregation_settings(override):
    from apps.operations.report_charts_remaining import table
    with pytest.raises(ValueError):
        validate_chart_spec({**table("id"), **override}, ("id", "makerspace_id"))


@pytest.mark.django_db
@pytest.mark.parametrize("key", ["platform-services", "platform-usage"])
@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_platform_analytics_response_includes_definition_chart_spec(monkeypatch, key, grain):
    actor = make_user("chart-platform-admin", role=User.Role.SUPERADMIN,
                      access_status=User.AccessStatus.ACTIVE)
    definition = REPORT_REGISTRY[key]
    captured = []

    def build(makerspace_id=None, **kwargs):
        assert makerspace_id is None
        assert require_platform_context(kwargs["platform_context"]).actor.pk == actor.pk
        captured.append(kwargs)
        return ReportResult(definition.fields, [])

    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: build)
    response = authenticated_client(actor).get(f"/api/v1/admin/platform/analytics/{key}?grain={grain}")
    assert response.status_code == 200, response.data
    assert response.data["chart_spec"] == definition.chart_spec
    assert response.data["chart_spec"] is not None
    assert captured[0]["grain"] == grain
    serializer = PlatformAnalyticsReportSerializer(data=response.data)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize("key,status,date_field", [
    ("active-loans", "issued", "issued_at"), ("returns", "returned", "closed_at"),
])
def test_loan_detail_charts_count_rows_instead_of_request_ids(key, status, date_field):
    space = make_space("chart-loan-count")
    actor = make_member("chart-loan-member", space)
    for _ in range(2):
        HardwareRequest.objects.create(makerspace=space, requester=actor, status=status,
                                       **{date_field: timezone.now()})
    payload = reports.report_data(key, space.pk, actor=actor)
    assert len(payload["typed_rows"]) == 2
    assert [row["count"] for row in payload["typed_rows"]] == [1, 1]
    assert sum(row["count"] for row in payload["typed_rows"]) == 2
    assert REPORT_REGISTRY[key].chart_spec["values"] == [{"field": "count", "unit": "loans"}]


@pytest.mark.django_db
def test_local_health_chart_x_field_is_present_in_real_output():
    space = make_space("chart-health")
    payload = reports.report_data("fablab-health", space.pk)
    assert payload["typed_rows"][0]["makerspace_id"] == space.pk
