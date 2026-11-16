"""#183B gap 13: a report whose source module or capability is off is HIDDEN, not listed disabled."""

import pytest
from django.urls import reverse

from apps.operations.report_registry import REPORT_DEFINITIONS
from apps.operations.report_sources import definition_live
from tests.module_helpers import disable_module
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def _with_modules(slug, *modules):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports", *modules})
    space.save(update_fields=["enabled_modules"])
    return space


def _catalog(space, user):
    response = authenticated_client(user).get(reverse("report-catalog", args=[space.pk]))
    assert response.status_code == 200, response.data
    return {row["key"]: row for row in response.data["results"]}


def test_off_module_reports_are_absent_and_come_back_when_switched_on():
    space = _with_modules("reports-hidden", "bulk_import")
    manager = make_member("reports-hidden-manager", space)
    assert "import-quality" in _catalog(space, manager)

    disable_module(space, "bulk_import")
    rows = _catalog(space, manager)
    assert "import-quality" not in rows
    # Every listed row is live: nothing is shown disabled.
    assert all(row["available"] is True and row["unavailable_reason"] is None for row in rows.values())

    space.refresh_from_db()
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bulk_import"})
    space.save(update_fields=["enabled_modules"])
    assert "import-quality" in _catalog(space, manager)


def test_definition_live_follows_modules_and_capabilities():
    space = _with_modules("reports-live")
    for definition in REPORT_DEFINITIONS:
        if definition.platform_only or definition.subject_kind:
            continue
        live = definition_live(space, definition)
        if definition.required_feature and definition.required_feature not in (space.enabled_features or []):
            assert live is False, definition.key


def test_schedules_of_hidden_reports_are_hidden_but_kept():
    from django.utils import timezone
    from apps.operations.models_report_schedules import ReportSchedule

    space = _with_modules("reports-schedules-hidden", "bulk_import")
    manager = make_member("reports-schedules-hidden-manager", space)
    ReportSchedule.objects.create(makerspace=space, report_key="import-quality", next_run_at=timezone.now(),
                                  created_by=manager)
    url = reverse("report-schedules", args=[space.pk])
    shown = authenticated_client(manager).get(url)
    assert shown.status_code == 200, shown.data
    assert "import-quality" in {row["report_key"] for row in shown.data.get("results", shown.data)}

    disable_module(space, "bulk_import")
    hidden = authenticated_client(manager).get(url)
    assert hidden.status_code == 200
    assert "import-quality" not in {row["report_key"] for row in hidden.data.get("results", hidden.data)}
    # Kept, and skipped by the runner rather than deleted.
    assert ReportSchedule.objects.filter(makerspace=space, report_key="import-quality").exists()
