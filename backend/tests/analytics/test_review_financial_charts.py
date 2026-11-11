"""Derived financial totals must never stack with their components."""

import pytest

from apps.operations.report_registry import report_definition


@pytest.mark.parametrize("key", ["revenue-over-time", "cash-book"])
def test_money_components_and_net_are_independent_lines(key):
    definition = report_definition(key)
    assert definition.chart_hint == "multi_line"
    assert {value["field"] for value in definition.chart_spec["values"]} >= {"collected_amount", "net_amount"}
    assert definition.chart_spec["partition"] == "currency"
    assert definition.chart_spec["negatives"] == "allow"
