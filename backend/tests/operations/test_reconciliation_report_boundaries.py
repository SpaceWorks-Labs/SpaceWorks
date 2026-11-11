"""Reports retain action boundaries, table metadata and inbox-independent push counts."""
from datetime import date

import pytest
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.models import DeviceGrant, NativeAppRegistration
from apps.integrations.models import EmailLog, PushDevice
from apps.notifications.models_push import MemberPushDelivery
from apps.operations import dashboard_widgets
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.reports_communications import build_communications_health
from apps.operations.reports_mobile_auth import build_mobile_auth
from apps.operations.views_report_helpers import date_range_from_dates
from tests.operations.reconciliation_report_helpers import at, delivery, report_space
from tests.return_helpers import authenticated_client, make_member
from apps.makerspaces.models import MakerspaceMembership

pytestmark = pytest.mark.django_db


def test_communications_requires_space_manager_and_never_crosses_staff_tenant():
    space, other = report_space("recon-r-auth"), report_space("recon-r-other")
    manager = make_member("recon-r-manager", space)
    inventory = make_member("recon-r-inventory", space, membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER)
    delivery(space)
    route = f"/api/v1/admin/makerspace/{space.pk}/analytics/communications-health"
    assert authenticated_client(manager).get(route).status_code == 200
    assert authenticated_client(inventory).get(route).status_code == 403
    foreign = f"/api/v1/admin/makerspace/{other.pk}/analytics/communications-health"
    assert authenticated_client(manager).get(foreign).status_code == 404


def test_identity_widget_requires_both_domain_and_audit_authority(monkeypatch):
    space = report_space("recon-r-identity")
    space.enabled_modules += ["machines"]
    space.save(update_fields=["enabled_modules"])
    actor = make_member("recon-r-identity-reader", space)
    allowed = {rbac.Action.MANAGE_MACHINES}
    monkeypatch.setattr(dashboard_widgets.rbac, "can", lambda user, action, tenant: action in allowed)
    assert "machine-usage-members" not in {w.key for w in dashboard_widgets.visible_widgets(actor, space)}
    allowed.add(rbac.Action.VIEW_AUDIT)
    assert "machine-usage-members" in {w.key for w in dashboard_widgets.visible_widgets(actor, space)}
    assert not REPORT_REGISTRY["machine-usage-members"].deployment_aggregate


def test_presence_coverage_and_event_booking_table_contracts_survive_union():
    assert "presence-activity" in REPORT_MODULE_COVERAGE["presence"].reports
    for key in ("event-registrations", "event-feedback", "booking-reservations", "booking-answers"):
        definition = REPORT_REGISTRY[key]
        assert definition.subject_kind and not definition.schedulable and not definition.deployment_aggregate
        assert definition.chart_spec["values"] == []
        assert definition.chart_spec["x"]["field"] in definition.fields


def test_email_parent_is_not_counted_again_beside_provider_ledger_and_personal_chat_is_counted():
    space = report_space("recon-r-physical-ledgers")
    space.enabled_modules += ["email", "telegram"]
    space.save(update_fields=["enabled_modules"])
    delivery(space, channel="email", state="sent")
    delivery(space, channel="telegram", state="sent")
    EmailLog.objects.create(makerspace=space, to_email="PRIVATE@example.test", subject="PRIVATE SUBJECT",
        text_body="PRIVATE BODY", status="sent", attempts=1, provider_source="platform")
    rows = build_communications_health(space.pk).records
    assert sum(row["delivery_count"] for row in rows if row["channel"] == "email") == 1
    assert sum(row["delivery_count"] for row in rows if row["channel"] == "telegram") == 1
    assert "PRIVATE" not in str(rows)


def test_mobile_auth_calendar_labels_use_local_midnight_before_sql_filter():
    from apps.audit.models import AuditLog
    space = report_space("recon-r-mobile-calendar")
    space.enabled_modules += ["mobile"]
    space.save(update_fields=["enabled_modules"])
    for stamp in ("2026-03-07T18:29:59", "2026-03-07T18:30:00"):
        AuditLog.objects.create(makerspace=space, action="auth.device_login_succeeded", created_at=at(stamp),
            meta={"platform": "android", "environment": "production"})
    result = build_mobile_auth(space.pk, date_range=date_range_from_dates(date(2026, 3, 8), date(2026, 3, 8)))
    assert sum(row["count"] for row in result.records) == 1
    assert result.records[0]["period"] == "2026-03-08"


def test_push_counts_device_child_once_with_no_inbox_or_notifications_module():
    space = report_space("recon-r-push-no-inbox")
    space.enabled_modules += ["mobile"]
    space.save(update_fields=["enabled_modules"])
    parent = delivery(space, channel="native_push", state="sent")
    user, now = parent.envelope.recipient, timezone.now()
    registration = NativeAppRegistration.objects.create(makerspace=space, app_id="r.test", platform="android",
        environment="development", verifier_config_key="test", status="approved")
    grant = DeviceGrant.objects.create(registration=registration, user=user, platform="android", app_id="r.test",
        environment="development", signing_identity="r-signer", attestation_subject_fingerprint="a" * 64,
        attested_at=now, last_used_at=now)
    device = PushDevice.objects.create(makerspace=space, user=user, device_grant=grant, provider="fcm",
        environment="development", token_ciphertext="encrypted-test-token", token_fingerprint="b" * 64)
    parents = [field for field in MemberPushDelivery._meta.fields if field.is_relation
               and field.related_model._meta.label_lower == "integrations.notificationdelivery"]
    assert len(parents) == 1, "P must supply the canonical parent before lane R's integration suite runs"
    MemberPushDelivery.objects.create(**{parents[0].name: parent}, inbox_row=None, push_device=device,
        platform="android", provider_source="platform", status="sent", attempts=2)
    rows = [r for r in build_communications_health(space.pk).records if r["channel"] == "native_push"]
    assert len(rows) == 1 and rows[0]["delivery_count"] == rows[0]["sent_count"] == 1
    assert rows[0]["attempt_count"] == 2 and rows[0]["feature"] == "bookings"
    assert rows[0]["audience"] == "requester" and "PRIVATE" not in str(rows)
