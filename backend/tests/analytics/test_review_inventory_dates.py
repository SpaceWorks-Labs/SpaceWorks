"""Stage-4 regressions: local calendar labels across preview/export/org paths."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from apps.makerspaces.models import Makerspace
from apps.operations.org_reports import organization_report_data
from apps.operations.report_registry import report_definition
from apps.operations.report_scope import combined_report_scope
from apps.operations.reports import report_data, report_rows
from apps.operations.reports_ab_consumables import build_consumable_usage
from apps.operations.views_report_helpers import date_range_from_dates
from tests.analytics.test_ab_consumables_m1f2 import pool
from tests.analytics.test_ab_inventory_m1f2 import enable, loan
from tests.return_helpers import make_member, make_product, make_space
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "America/New_York"])
def test_calendar_labels_match_preview_export_and_organization(zone):
    space = make_space("review-local-day")
    space.timezone = zone
    space.save(update_fields=["timezone"])
    enable(space, "request_workflow")
    actor = make_member("review-local-reader", space)
    selected = datetime(2026, 10, 17, 1, tzinfo=ZoneInfo(zone))
    for at, label in ((selected, "Selected"), (selected + timedelta(days=1), "Next"),
                      (selected - timedelta(days=1), "Previous")):
        loan(space, actor, make_product(space, name=label), at=at)
    bounds = date_range_from_dates(date(2026, 10, 17), date(2026, 10, 17))
    preview = report_data("most-lent", space.pk, date_range=bounds)["typed_rows"]
    exported = report_rows("most-lent", space.pk, date_range=bounds)
    org = organization_report_data(report_definition("most-lent"),
        combined_report_scope(Makerspace.objects.filter(pk=space.pk)), date_range=bounds, limit=100)
    assert {row["product_name"] for row in preview} == {"Selected"}
    assert {row[exported[0].index("product_name")] for row in exported[1:]} == {"Selected"}
    assert {row["product_name"] for row in org["total"]["rows"]} == {"Selected"}
    # A precise UTC tuple selects a different cohort and must not be rebound.
    precise = tuple(bounds)
    expected = "Next" if zone == "Asia/Kolkata" else "Selected"
    assert {row["product_name"] for row in report_data("most-lent", space.pk,
        date_range=precise)["typed_rows"]} == {expected}


def test_consumption_uses_local_day_before_reading_sources():
    from apps.machines.models import MachineConsumableAdjustment, MachineUsageEntry

    space = make_space("review-consumption-day")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    enable(space, "machines")
    actor = make_member("review-consumption-reader", space)
    target = machine(space)
    stock = pool(space, target)
    usage = MachineUsageEntry.objects.create(machine=target, hours=1)
    for day, quantity in ((16, 2), (17, 9)):
        # 20:00 UTC falls on the next tenant day.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, day, 20, tzinfo=timezone.utc)):
            MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=stock,
                kind="manual", usage_entry=usage, quantity_delta=-quantity)
    bounds = date_range_from_dates(date(2026, 10, 17), date(2026, 10, 17))
    rows = build_consumable_usage(space.pk, actor=actor, date_range=bounds).records
    assert [(str(row["period"]), row["consumed_quantity"]) for row in rows] == [("2026-10-17", 2)]
