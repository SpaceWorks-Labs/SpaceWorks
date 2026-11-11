"""The per-space financial year (#71): helpers, the finance-setting endpoint and its authority."""
from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.financial_year import fy_bounds, fy_label, fy_presets
from tests.makerspaces.l4_helpers import space_with_manager
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def test_april_default_bounds_and_labels():
    space = make_space("fy-default")
    assert space.financial_year_start_month == 4
    assert fy_bounds(space, date(2026, 3, 31)) == (date(2025, 4, 1), date(2026, 3, 31))
    assert fy_bounds(space, date(2026, 4, 1)) == (date(2026, 4, 1), date(2027, 3, 31))
    assert fy_label(space, date(2026, 10, 1)) == "2026-27"


def test_january_start_is_a_calendar_year_label():
    space = make_space("fy-jan")
    space.financial_year_start_month = 1
    assert fy_bounds(space, date(2026, 6, 1)) == (date(2026, 1, 1), date(2026, 12, 31))
    assert fy_label(space, date(2026, 6, 1)) == "2026"


def test_datetime_is_read_on_the_space_wall_clock():
    space = make_space("fy-tz")
    space.timezone = "Asia/Kolkata"
    # 31 March 20:00 UTC is already 1 April in India: the new year.
    assert fy_bounds(space, datetime(2026, 3, 31, 20, 0, tzinfo=dt_timezone.utc))[0] == date(2026, 4, 1)


def test_presets_walk_back_whole_years():
    space = make_space("fy-presets")
    presets = fy_presets(space, date(2026, 5, 1))
    assert [row["label"] for row in presets] == ["FY 2026-27", "FY 2025-26", "FY 2024-25"]


def test_space_manager_changes_it_with_two_audit_rows():
    space, manager = space_with_manager("fy-api")
    url = reverse("admin-financial-year", args=[space.pk])
    client = authenticated_client(manager)
    assert client.get(url).json()["financial_year_start_month"] == 4
    response = client.put(url, {"financial_year_start_month": 1}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["current_label"].isdigit()
    space.refresh_from_db()
    assert space.financial_year_start_month == 1
    assert AuditLog.objects.filter(action="makerspace.financial_year_updated").count() == 1
    changed = AuditLog.objects.get(action="settings.changed", meta__key="finance.financial_year_start_month")
    assert changed.meta["from"] == 4 and changed.meta["to"] == 1


def test_it_is_never_delegable_to_a_members_manager():
    space = make_space("fy-deny")
    inventory = make_member("fy-deny-inv", space, membership_role="inventory_manager")
    response = authenticated_client(inventory).put(
        reverse("admin-financial-year", args=[space.pk]), {"financial_year_start_month": 7}, format="json")
    assert response.status_code == 403
    space.refresh_from_db()
    assert space.financial_year_start_month == 4


def test_invalid_month_is_refused():
    space, manager = space_with_manager("fy-bad")
    response = authenticated_client(manager).put(
        reverse("admin-financial-year", args=[space.pk]), {"financial_year_start_month": 13}, format="json")
    assert response.status_code == 400
