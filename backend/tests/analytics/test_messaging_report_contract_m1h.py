"""Schema and infrastructure guards for the addressed messaging extension."""

from copy import deepcopy

import pytest

from apps.operations.org_report_strategies import STRATEGIES
# R3: PLATFORM_SERVICES was removed by b13f361e (#110, no hidden bucket); the channel check stays on the report.
from apps.operations.report_condition_metrics import condition_metrics
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.report_coverage_contract import REPORT_COVERAGE_CONTRACT
from apps.operations.report_fields_hi import MESSAGING_COUNTS, MESSAGING_STATUS_COUNTS
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_validation import validate_chart_spec, validate_report_definition
from apps.operations.serializers_report_chart import ReportChartSpecSerializer
from apps.operations.serializers_reports_messaging import CommunicationsHealthRowSerializer, PlatformServicesRowSerializer


def test_report_allowlists_schemas_conditions_and_coverage_agree():
    communications, services = (REPORT_REGISTRY[key] for key in ("communications-health", "platform-services"))
    for definition, serializer in ((communications, CommunicationsHealthRowSerializer), (services, PlatformServicesRowSerializer)):
        validate_report_definition(definition)
        assert set(definition.fields) == set(serializer().fields)
    # Lane R rebuilt both on canonical delivery records (communications 4, services 3).
    assert communications.version == 4 and services.version == 3
    assert set(MESSAGING_COUNTS) <= set(condition_metrics(communications))
    for channel in ("sms", "whatsapp"):
        assert channel in communications.section_modules
        assert set(REPORT_COVERAGE_CONTRACT[channel]) <= set(REPORT_MODULE_COVERAGE[channel].reports)
    strategy = STRATEGIES[communications.key]
    assert "consented_member_count" in strategy.breakdown_only_fields
    assert "consented_member_count" not in strategy.total_fields


def test_chart_stacks_only_exclusive_outcomes_and_keeps_rates_as_lines():
    definition = REPORT_REGISTRY["communications-health"]
    spec = definition.chart_spec
    values = {row["field"]: row for row in spec["values"]}
    assert all(values[field]["kind"] == "stacked_bar" for field in MESSAGING_STATUS_COUNTS)
    assert values["sent_count"]["kind"] == "line"  # Cumulative, overlaps delivered/read.
    assert values["delivery_rate"]["kind"] == values["read_rate"]["kind"] == "line"
    assert "channel" in spec["series"] and spec["x"]["field"] == "period"
    serializer = ReportChartSpecSerializer(data=spec)
    assert serializer.is_valid(), serializer.errors
    malformed = deepcopy(spec)
    malformed["values"][0]["kind"] = "pie"
    with pytest.raises(ValueError, match="kind"):
        validate_chart_spec(malformed, definition.fields)
