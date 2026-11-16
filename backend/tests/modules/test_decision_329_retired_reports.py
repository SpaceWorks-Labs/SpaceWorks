"""Decision 329 (b): the certification reports are read-only history of a retired feature.

Titled "(retired)", listed only for a space with certification records, never newly schedulable,
while a schedule that already exists keeps running and the manual export keeps working.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.machines.models import MachineType
from apps.machines.models_certifications import CertificationType
from apps.operations.models_report_schedules import ReportSchedule
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_retired import RETIRED_REPORT_KEYS
from apps.operations.report_schedule_services import _skip_reason
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db
TITLES = {"certification-holders": "Certification history (retired)",
          "certification-coverage": "Certification coverage (retired)"}


def _space(slug, *, history):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports", "machines"})
    space.save(update_fields=["enabled_modules"])
    if history:
        kind = MachineType.objects.create(makerspace=space, slug=f"{slug}-laser", name="Laser")
        CertificationType.objects.create(makerspace=space, machine_type=kind, name="Laser induction")
    return space, make_member(f"{slug}-sm", space)


def _catalog(space, user):
    response = authenticated_client(user).get(reverse("report-catalog", args=[space.pk]))
    assert response.status_code == 200, response.data
    return {row["key"]: row for row in response.data["results"]}


def test_both_reports_are_titled_retired():
    assert set(TITLES) == RETIRED_REPORT_KEYS
    for key, title in TITLES.items():
        assert REPORT_REGISTRY[key].title == title


def test_they_are_listed_only_where_certification_records_exist():
    without, manager = _space("r329-none", history=False)
    assert not RETIRED_REPORT_KEYS & set(_catalog(without, manager))

    with_history, manager = _space("r329-history", history=True)
    rows = _catalog(with_history, manager)
    assert RETIRED_REPORT_KEYS <= set(rows)
    assert all(rows[key]["schedulable"] is False for key in RETIRED_REPORT_KEYS)


def test_a_new_schedule_is_refused():
    space, manager = _space("r329-schedule", history=True)
    response = authenticated_client(manager).post(
        f"/api/v1/admin/makerspaces/{space.pk}/report-schedules",
        {"report_key": "certification-coverage", "format": "csv", "cadence": "weekly",
         "recipient_emails": ["ops@example.test"]}, format="json")
    assert response.status_code == 400 and "retired" in str(response.data["report_key"])


def test_an_existing_schedule_keeps_running_and_stays_editable():
    space, manager = _space("r329-existing", history=True)
    row = ReportSchedule.objects.create(
        makerspace=space, report_key="certification-coverage", format="csv", cadence="weekly",
        next_run_at=timezone.now() - timedelta(minutes=1), created_by=manager, recipient_emails=["ops@example.test"])

    assert _skip_reason(row, REPORT_REGISTRY["certification-coverage"]) == ""
    edited = authenticated_client(manager).patch(reverse("report-schedule-detail", args=[row.pk]),
                                                 {"cadence": "monthly"}, format="json")
    assert edited.status_code == 200, edited.data


def test_the_manual_export_keeps_working():
    space, manager = _space("r329-export", history=True)
    response = authenticated_client(manager).get(
        reverse("report-export", args=[space.pk, "certification-coverage"]), {"format": "csv"})
    assert response.status_code == 200, getattr(response, "data", response.content[:200])
