from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.integrations.models import EmailLog, NotificationDeliveryLog, PushDevice
from apps.integrations.models_tracking import PushDeliveryAttempt
from apps.integrations.reports_communications import build_communications_health
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.report_fields_hi import COMMUNICATION_COUNTS, COMMUNICATION_GROUPS
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member, make_space
from tests.accounts.account_factories import device_grant
from tests.operations.reconciliation_report_helpers import delivery
from tests.test_native_push import push_member

pytestmark = pytest.mark.django_db
AT = datetime(2026, 10, 11, 20, tzinfo=UTC)


def email(space, status="sent", **kwargs):
    row = EmailLog.objects.create(makerspace=space, to_email="private@example.com",
                                  subject="secret message", text_body="private body", status=status, **kwargs)
    EmailLog.objects.filter(pk=row.pk).update(created_at=AT)
    return row


def inbox(space, user, read_at=None):
    row = NotificationInboxRow.objects.create(makerspace=space, user=user, title="private title",
        summary="private summary", feature="hardware_requests", event="accepted", event_key=uuid4(), read_at=read_at)
    NotificationInboxRow.objects.filter(pk=row.pk).update(created_at=AT)
    return row


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_email_local_grains_provider_outcomes_and_event_dates(grain, period):
    space, other = make_space("hi-mail"), make_space("hi-mail-other")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    email(space, provider_source="platform", attempts=2, bounced_at=AT, complained_at=AT)
    email(space, "failed", provider_source="own", attempts=1)
    email(space, "skipped", provider_source="own", error="email_address_suppressed")
    email(space, provider_source="")
    email(other, provider_source="own")
    rows = [r for r in build_communications_health(space.pk, grain=grain).records if r["channel"] == "email"]
    assert {r["period"] for r in rows} == {period}
    own = next(r for r in rows if r["provider_source"] == "own")
    assert (own["delivery_count"], own["failed_count"], own["suppressed_count"]) == (2, 1, 1)
    platform = next(r for r in rows if r["provider_source"] == "platform")
    assert (platform["sent_count"], platform["bounced_count"], platform["complained_count"]) == (1, 1, 1)
    assert platform["attempt_count"] == 2
    assert any(r["provider_source"] == "unknown" for r in rows)
    assert_report_disclosure_safe(rows)


def test_bounce_is_reported_when_original_send_is_outside_window():
    space = make_space("hi-bounce-window")
    email(space, provider_source="platform", bounced_at=datetime(2026, 10, 15, tzinfo=UTC))
    rows = [r for r in build_communications_health(space.pk, date_range=(datetime(2026, 10, 15, tzinfo=UTC),
                                                            datetime(2026, 10, 16, tzinfo=UTC))).records if r["channel"] == "email"]
    assert len(rows) == 1
    assert rows[0]["bounced_count"] == 1 and rows[0]["delivery_count"] == 0
    assert rows[0]["success_rate_percent"] is None


def test_chat_and_per_device_push_do_not_double_count_or_echo_content():
    space, other = make_space("hi-push"), make_space("hi-push-other")
    staff = make_member("hi-push-staff", space)
    member = push_member("hi-push-member", space)
    staff_device = PushDevice.objects.create(makerspace=space, user=staff, device_grant=device_grant(staff),
        provider="fcm", environment="development", token_ciphertext="private destination", token_fingerprint="f" * 64)
    member_device = PushDevice.objects.create(makerspace=space, user=member, device_grant=device_grant(member),
        provider="fcm", environment="development", token_ciphertext="private destination", token_fingerprint="m" * 64)
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="hardware_requests",
        event="accepted", status="sent", attempts=10, text_body="secret text", payload={"secret": "private"})
    PushDeliveryAttempt.objects.create(delivery_log=log, push_device=staff_device, platform="android",
                                       status="failed", last_error="invalid_token", attempts=3)
    # The canonical push parent is never counted beside its per-device children.
    parent = delivery(space, channel="native_push", state="sent", feature="hardware_requests", audience="member")
    MemberPushDelivery.objects.create(envelope_delivery=parent, inbox_row=inbox(space, member),
        push_device=member_device, platform="android", provider_source="platform", status="sent", attempts=1)
    PushDevice.objects.filter(pk__in=[staff_device.pk, member_device.pk]).update(active=False, invalidated_at=AT)
    NotificationDeliveryLog.objects.create(makerspace=space, channel="slack", feature="hardware_requests",
                                           event="accepted", status="failed", attempts=2)
    NotificationDeliveryLog.objects.create(makerspace=other, channel="slack", feature="hardware_requests", event="accepted")
    rows = build_communications_health(space.pk).records
    push = {r["audience"]: r for r in rows if r["channel"] == "native_push"}
    assert set(push) == {"staff", "member"}
    counts = ("delivery_count", "attempt_count", "sent_count", "invalid_count", "failed_count")
    assert tuple(push["staff"][c] for c in counts) == (1, 3, 0, 1, 0)
    assert tuple(push["member"][c] for c in counts) == (1, 1, 1, 0, 0)
    assert push["member"]["success_rate_percent"] == Decimal("100.00")
    assert push["staff"]["success_rate_percent"] == Decimal("0.00")
    chat = next(r for r in rows if r["channel"] == "slack")
    assert (chat["triggered_count"], chat["failed_count"], chat["attempt_count"]) == (1, 1, 2)
    assert_report_disclosure_safe(rows)


def test_personal_inbox_cohort_rate_and_sections_are_gated():
    space = make_space("hi-inbox")
    user = make_member("hi-inbox-user", space)
    inbox(space, user, datetime(2026, 10, 12, tzinfo=UTC))
    inbox(space, user, datetime(2026, 10, 20, tzinfo=UTC))
    inbox(space, user)
    rows = build_communications_health(space.pk, date_range=(None, datetime(2026, 10, 16, tzinfo=UTC))).records
    row = next(r for r in rows if r["channel"] == "in_app")
    assert (row["inbox_created_count"], row["inbox_read_count"], row["unread_count"]) == (3, 1, 2)
    assert row["read_rate_percent"] == Decimal("33.33")
    space.enabled_modules = ["reports"]
    space.save(update_fields=["enabled_modules"])
    email(space, provider_source="platform")
    assert build_communications_health(space.pk).records == []


@pytest.mark.parametrize("module,channel", [("email", "email"), ("slack", "slack"),
                                           ("notifications", "in_app"), ("mobile", "native_push")])
def test_each_communication_section_omits_disabled_source(module, channel):
    space = make_space("hi-section")
    user = make_member("hi-section-user", space)
    email(space)
    inbox(space, user)
    NotificationDeliveryLog.objects.create(makerspace=space, channel="slack", feature="hardware_requests", event="accepted")
    device = PushDevice.objects.create(makerspace=space, user=user, device_grant=device_grant(user, platform="apple"), provider="apns",
        environment="development", token_ciphertext="private destination", token_fingerprint="s" * 64)
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="hardware_requests", event="accepted")
    PushDeliveryAttempt.objects.create(delivery_log=log, push_device=device, platform="apple", status="sent")
    assert channel in {r["channel"] for r in build_communications_health(space.pk).records}
    space.enabled_modules.remove(module)
    space.save(update_fields=["enabled_modules"])
    rows = build_communications_health(space.pk).records
    assert channel not in {r["channel"] for r in rows}
    assert rows  # Unrelated installed sections remain available.


def test_organization_sums_rate_denominators_and_preserves_partitions():
    def row(created, read, sent, delivered, **dimensions):
        return {**dict.fromkeys(COMMUNICATION_GROUPS, "unknown"), **dict.fromkeys(COMMUNICATION_COUNTS, 0),
                "period": "2026-10-12", "channel": "in_app", "inbox_created_count": created,
                "inbox_read_count": read, "sent_count": sent, "delivery_count": delivered,
                "last_activity_at": AT, **dimensions}
    rows = aggregate_rows("communications-health", [(1, [row(1, 1, 1, 1)]),
        (2, [row(9, 0, 0, 9), row(1, 1, 1, 1, provider_source="own")])], limit=100)
    combined = next(r for r in rows if r["provider_source"] == "unknown")
    assert combined["read_rate_percent"] == combined["success_rate_percent"] == Decimal("10.00")
    assert combined["last_activity_at"] == AT and len(rows) == 2
    assert_report_disclosure_safe(rows)
