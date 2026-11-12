"""The member's job page lists what they may report, and only once the job is running (decision 341)."""
import pytest
from django.urls import reverse

from apps.machines import consumable_usage as usage
from tests.machines.eta_helpers import job

from .helpers import define, running_job, world

pytestmark = pytest.mark.django_db


def test_job_detail_lists_member_reportable_consumables_with_recorded_amounts():
    w = world("rep-member")
    define(w, "tape", unit="m", record_by=["staff", "member"])
    define(w, "sheet", record_by=["staff"])
    row, member = running_job(w)
    from .helpers import client
    url = reverse("member-machine-job-detail", kwargs={"pk": row.pk})
    listed = client(member).get(url).data["report_consumables"]
    assert [(item["key"], item["recorded_quantity"]) for item in listed] == [("tape", None)]
    usage.record_actuals(row, member, [{"key": "tape", "quantity": "2.5"}], source="member")
    listed = client(member).get(url).data["report_consumables"]
    assert listed[0]["recorded_quantity"] == "2.500"


def test_nothing_to_report_before_staff_accept_the_job_or_on_the_list():
    w = world("rep-pending")
    define(w, "tape", unit="m", record_by=["member"])
    pending = job(w)
    assert usage.member_reportable(pending) == []
    from .helpers import client
    rows = client(pending.member).get(reverse("member-machine-jobs")).data
    rows = rows.get("results", rows) if isinstance(rows, dict) else rows
    assert all(item["report_consumables"] == [] for item in rows)
