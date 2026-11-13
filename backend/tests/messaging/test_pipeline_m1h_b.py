from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.dispatch import enqueue_addressed_messages
from apps.integrations.messaging.eligibility import eligibility, reserve_quota
from apps.integrations.models import MessagingDelivery, NotificationPreference
from apps.integrations.recipients_addressed import addressed_recipients
from apps.makerspaces.models import MakerspaceMembership
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.messaging.helpers_m1h_b import setup_pipeline

RETIRED = "Legacy MessagingDelivery pipeline retired by the D1 notification reconciliation (decisions 285/297: one canonical envelope -> NotificationDelivery pipeline sent from the Celery dispatcher); enqueue_addressed_messages/worker.deliver/sweep are inert shims. Behaviour is covered by tests/messaging/test_delivery_rechecks_m1h.py, test_barrier_m1h_b.py, test_concurrency_m1h_b.py, test_webhooks_m1h_b.py."
pytestmark = [pytest.mark.django_db, pytest.mark.skip(reason=RETIRED)]


@pytest.fixture
def pipeline(space, member):
    return setup_pipeline(space, member)


def test_dedupe_and_quota_reserved_once(pipeline):
    with patch("apps.makerspaces.limits.reserve_notification_quota", return_value=True) as quota:
        first = pipeline.enqueue()
        second = pipeline.enqueue()
        assert first.pk == second.pk
        assert reserve_quota(first)
        # One reservation per actual recipient, never per enqueue/retry.
        assert quota.call_count == MessagingDelivery.objects.filter(channel="sms", quota_reserved_at__isnull=False).count()
    assert first.quota_reserved_at


def test_quota_exhaustion_and_skipped_rows(pipeline):
    with patch("apps.makerspaces.limits.reserve_notification_quota", return_value=False):
        row = pipeline.enqueue()
    assert (row.status, row.skip_reason, row.quota_reserved_at) == ("skipped", "quota_exceeded", None)


def test_crash_between_reservation_and_dispatch_preserves_single_charge(pipeline, django_capture_on_commit_callbacks):
    with patch("apps.makerspaces.limits.reserve_notification_quota", return_value=True) as quota:
        with django_capture_on_commit_callbacks(execute=True), patch(
            "apps.integrations.tasks_messaging.deliver_messaging_task.delay", side_effect=RuntimeError("broker down")):
            rows = enqueue_addressed_messages(pipeline.space, feature="hardware_requests", event="accepted",
                event_key="broker-failure", payload=pipeline.payload, channels=("sms",))
        before = quota.call_count
        pipeline.enqueue(key="broker-failure")
        assert quota.call_count == before
    assert all(row.quota_reserved_at for row in rows if row.status == "pending")


@pytest.mark.parametrize("change,reason", [
    ("consent", "no_consent"), ("membership", "no_tenant_tie"), ("receives", "membership_opted_out"),
    ("account", "account_inactive"), ("phone", "phone_unverified"), ("matrix", "matrix_disabled"),
    ("module", "module_disabled"), ("source", "source_changed"),
])
def test_changes_after_enqueue_skip_at_delivery(pipeline, change, reason):
    from apps.integrations.messaging.worker import deliver
    row = pipeline.enqueue()
    user, space = pipeline.member, pipeline.space
    if change == "consent":
        grant_consent(user=user, makerspace_id=space.pk, channel="sms", action="opted_out")
    elif change in {"membership", "receives"}:
        values = {"status": "revoked"} if change == "membership" else {"receives_notifications": False}
        MakerspaceMembership.objects.filter(user=user, makerspace=space).update(**values)
    elif change == "account":
        user.is_active = False
        user.save(update_fields=["is_active"])
    elif change == "phone":
        user.phone_verified_at = None
        user.save(update_fields=["phone_verified_at"])
    elif change == "matrix":
        NotificationPreference.objects.filter(makerspace=space, channel="sms").update(enabled=False)
    elif change == "module":
        space.enabled_modules = [key for key in space.enabled_modules if key != "sms"]
        space.save(update_fields=["enabled_modules"])
    else:
        pipeline.request.delete()
    with patch("apps.integrations.messaging.worker.send_message") as send:
        deliver(row.pk)
    row.refresh_from_db()
    assert (row.status, row.skip_reason) == ("skipped", reason)
    send.assert_not_called()


def test_permission_loss_is_rechecked(pipeline, manager):
    from apps.integrations.messaging.worker import deliver
    manager.phone_e164 = "+14155552672"
    manager.save(update_fields=["phone_e164"])
    manager.phone_verified_at = timezone.now()
    manager.save(update_fields=["phone_verified_at"])
    grant_consent(user=manager, makerspace_id=pipeline.space.pk, channel="sms", action="opted_in")
    with patch("apps.integrations.messaging.dispatch.schedule_delivery"):
        rows = enqueue_addressed_messages(pipeline.space, feature="hardware_requests", event="accepted", event_key="staff",
                                          payload=pipeline.payload, channels=("sms",))
    row = next(row for row in rows if row.user_id == manager.pk)
    assert row.status == "pending"
    assign_builtin_roles(manager, pipeline.space, "member")
    with patch("apps.integrations.messaging.worker.send_message") as send:
        deliver(row.pk)
    row.refresh_from_db()
    assert row.skip_reason == "recipient_changed"
    send.assert_not_called()


def test_inbox_disabled_does_not_disable_messaging_and_member_wording_wins(pipeline):
    assign_builtin_roles(pipeline.member, pipeline.space, "space_manager")
    pipeline.space.enabled_modules = [key for key in pipeline.space.enabled_modules if key != "notifications"]
    pipeline.space.save(update_fields=["enabled_modules"])
    selected = dict(addressed_recipients(pipeline.space, "hardware_requests", "accepted", pipeline.payload))
    assert selected[pipeline.member.pk] == "member"
    row = pipeline.enqueue()
    assert row.audience == "member" and row.status == "pending"


def test_account_only_owner_extracted_and_admitted_to_messaging(pipeline):
    MakerspaceMembership.objects.filter(user=pipeline.member, makerspace=pipeline.space).delete()
    assert (pipeline.member.pk, "member") in addressed_recipients(pipeline.space, "hardware_requests", "accepted", pipeline.payload)
    row = pipeline.enqueue()
    assert row.status == "pending" and row.skip_reason == ""


def test_personal_optout_and_tombstoned_preferences(pipeline):
    from apps.notifications.models import MemberNotificationPreference
    MemberNotificationPreference.objects.create(makerspace=pipeline.space, user=pipeline.member,
        feature="hardware_requests", channel="sms", enabled=False)
    assert pipeline.enqueue().skip_reason == "personal_disabled"
    with patch("apps.integrations.messaging.eligibility.apps.is_installed", return_value=False), patch(
        "apps.notifications.preferences.personal_enabled", side_effect=AssertionError("optional app imported")):
        assert pipeline.enqueue(key="tombstoned").status == "pending"


def test_stored_source_scope_is_revalidated(pipeline):
    from apps.integrations.messaging.worker import deliver
    row = pipeline.enqueue()
    MessagingDelivery.objects.filter(pk=row.pk).update(scope={"machine_type_id": 999})
    with patch("apps.integrations.messaging.worker.send_message") as send:
        deliver(row.pk)
    row.refresh_from_db()
    assert row.skip_reason == "source_changed"
    send.assert_not_called()


def test_sender_unavailable_and_missing_template_are_explicit_skips(pipeline):
    from apps.integrations.models import PlatformSmsSettings, WhatsAppTemplateBinding
    PlatformSmsSettings.objects.update(notifications_enabled=False)
    assert pipeline.enqueue().skip_reason == "sender_unavailable"
    WhatsAppTemplateBinding.objects.update(is_active=False)
    assert pipeline.enqueue(channel="whatsapp").skip_reason == "no_template"


def test_inbox_member_wording_staff_wording_and_disabled_member_fallback_unchanged(pipeline, manager):
    from uuid import uuid4
    from apps.notifications.inbox import write_matrix_inbox
    from apps.notifications.models import NotificationInboxRow
    assign_builtin_roles(pipeline.member, pipeline.space, "space_manager")
    pipeline.space.enabled_features = [*pipeline.space.enabled_features, "notifications.member_inbox"]
    pipeline.space.save(update_fields=["enabled_features"])
    first = uuid4()
    write_matrix_inbox(pipeline.space, "hardware_requests", "accepted", pipeline.payload, first)
    rows = NotificationInboxRow.objects.filter(event_key=first)
    assert rows.get(user=pipeline.member).summary == "Member wording"
    assert rows.get(user=manager).summary == "Staff wording"
    pipeline.space.enabled_features = [key for key in pipeline.space.enabled_features if key != "notifications.member_inbox"]
    pipeline.space.save(update_fields=["enabled_features"])
    second = uuid4()
    write_matrix_inbox(pipeline.space, "hardware_requests", "accepted", pipeline.payload, second)
    row = NotificationInboxRow.objects.get(user=pipeline.member, event_key=second)
    assert row.audience == "staff" and row.summary == "Staff wording"
