"""NCA audit 0.12.0 (decision 330): notification catalogue checks the earlier notification audits did not pin.

* Every catalogue event has a translated frontend label (34 fell back to the raw code, e.g. "shop order new").
* The machine-access expiry notice fans out one tenant boundary per grant (it wrote across tenants unguarded).
* The decision-328a limit notices are deterministic per (space, key, level, month, person): never double-posted.
"""
import re
from pathlib import Path

import pytest

from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.tenant_migration import gate_policy

LABELS = Path(__file__).resolve().parents[3] / "frontend/src/features/notifications/notificationEventLabels.ts"


@pytest.mark.skipif(not LABELS.exists(), reason="frontend tree not mounted")
def test_every_catalogue_event_has_a_translated_frontend_label():
    labelled = set(re.findall(r'(?:^|[\s{,])"?([a-z0-9_.]+)"?\s*:\s*t`', LABELS.read_text(encoding="utf-8"), re.M))
    missing = sorted({event for events in FEATURE_EVENTS.values() for event in events} - labelled)
    assert not missing, missing


def test_machine_access_expiry_notices_take_a_tenant_boundary_per_grant():
    from apps.space_controls.write_policy import READ_ONLY_OPERATIONS
    assert "apps.machines.notifications_machine_access.notify_expiring" in gate_policy.FANOUT_GATE_PARTICIPANTS
    assert "machine_access_expiry" in READ_ONLY_OPERATIONS


@pytest.mark.django_db
def test_a_limit_threshold_notice_is_posted_once_per_level_and_month():
    from apps.managed_hosting.limit_notices import notify_threshold
    from apps.notifications.models_inbox import NotificationInboxRow
    from tests.return_helpers import make_member, make_space
    from apps.makerspaces.models import MakerspaceMembership
    space = make_space("nca-limit-dedupe")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications"})
    space.save(update_fields=["enabled_modules"])
    make_member("nca-limit-manager", space, membership_role=MakerspaceMembership.Role.SPACE_MANAGER)
    for _ in range(2):
        notify_threshold(space, "events_monthly", "events", 80, 81, "2026-11")
    warnings = NotificationInboxRow.objects.filter(makerspace=space, event="platform_limit.warning")
    assert warnings.count() == len({row.user_id for row in warnings}) >= 1


@pytest.mark.django_db(transaction=True)
def test_an_adapter_job_report_held_for_review_tells_staff_once():
    from apps.devices.adapter_notifications import JOB_REVIEW
    from apps.devices.models import AdapterEvent
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from tests.parity_0120.adapter_api.test_job_dispatch import dispatched, lease_and_ack, report
    assert "adapter_job_review" in FEATURE_EVENTS["devices"]
    case = dispatched("nca-job-review")
    job = lease_and_ack(case)
    body, first = report(case, job, outcome="failed", failure_reason="nozzle_clog", percent_complete=40)
    assert first.status_code == 200, first.data
    assert case["sim"].post(f"jobs/{job['job_id']}/report", body).status_code == 200  # an identical replay
    rows = AdapterEvent.objects.filter(event_type=JOB_REVIEW, data__job_id=str(job["job_id"]))
    assert rows.count() == 1 and rows.get().data["outcome"] == "failed"
