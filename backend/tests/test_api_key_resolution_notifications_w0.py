from tests.accounts.account_factories import make_staff as staff_account
from collections import Counter
from unittest.mock import Mock

import pytest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.apiclients.models import ApiKeyRequest
from apps.apiclients.notifications import notify_api_key_request_resolved
from apps.audit.models import AuditLog
from apps.integrations import dispatch, dispatch_channels, telegram
from apps.integrations.models import (
    EmailLog, NotificationDeliveryLog, NotificationDestination,
    NotificationPreference,
)
from apps.integrations.notification_catalog import DEFAULT_CHANNEL_STATE, FEATURE_EVENTS
from apps.integrations.notification_enums import NotificationChannel, NotificationFeature
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.makerspaces import limits
from apps.makerspaces.models import MakerspaceMembership
from tests.module_helpers import disable_module
from tests.p3_fixbe_helpers import wire_outbox_worker
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db
FEATURE = NotificationFeature.API_ACCESS
EVENT = "api_key_request_resolved"


@pytest.fixture(autouse=True)
def delivery_workers(monkeypatch):
    wire_outbox_worker(monkeypatch)
    monkeypatch.setattr(dispatch_channels, "_enqueue_notification", lambda pk:
        dispatch_channels._deliver_notification(NotificationDeliveryLog.objects.get(pk=pk)))


@pytest.fixture
def deliver_resolution(django_capture_on_commit_callbacks):
    def deliver(row):
        with django_capture_on_commit_callbacks(execute=True):
            result = notify_api_key_request_resolved(row, sync=True)
        return result
    return deliver


def delivery_counts(space, state):
    """Personal mail and room transport results now live in separate ledgers."""
    counts = Counter(NotificationDelivery.objects.filter(
        makerspace=space, channel="email", state=state,
    ).values_list("channel", flat=True))
    counts.update(NotificationDeliveryLog.objects.filter(
        makerspace=space, status=state,
    ).values_list("channel", flat=True))
    return dict(counts)


def resolved_request(status="approved"):
    space = make_space("api-resolution")
    space.set_telegram_bot_token("private-bot-token")
    space.telegram_group_chat_id = "-100123"
    space.save(update_fields=["telegram_bot_token", "telegram_group_chat_id"])
    resolver = make_member("api-resolution-resolver", space)
    MakerspaceMembership.objects.filter(user=resolver, makerspace=space).update(receives_notifications=False)
    # Room delivery rechecks an eligible staff audience. The resolver opted out;
    # a separate staff account keeps room routing live without adding personal mail.
    staff_account(space, username="api-resolution-room-audience", email="")
    return ApiKeyRequest.objects.create(
        makerspace=space, requester=make_user("api-resolution-user", email_verified_at=timezone.now()), label="ERP",
        status=status, resolution_note="Private requester note", resolved_by=resolver, resolved_at=timezone.now(),
    )


def mute_email(space):
    NotificationPreference.objects.create(
        makerspace=space, feature=FEATURE, channel="email", enabled=False,
    )


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_resolution_uses_matrix_destinations_and_quota_without_private_chat_content(monkeypatch, status, deliver_resolution):
    row = resolved_request(status)
    destinations = [NotificationDestination.objects.create(
        makerspace=row.makerspace, channel="telegram", label=label,
        telegram_chat_id=chat_id,
    ) for label, chat_id in [("Ops", "-200"), ("Front desk", "-300")]]
    email = Mock(return_value=Mock(status=EmailLog.Status.SENT))
    send = Mock(return_value=True)
    reserve = Mock(return_value=True)
    monkeypatch.setattr(dispatch, "dispatch_email", email)
    monkeypatch.setattr(telegram, "send_message", send)
    monkeypatch.setattr(limits, "reserve_notification_quota", reserve)

    result = deliver_resolution(row)

    assert result.scheduled
    assert delivery_counts(row.makerspace, "sent") == {"email": 1, "telegram": 2}
    assert {call.kwargs["destination"].pk for call in send.call_args_list} == {d.pk for d in destinations}
    assert reserve.call_count == 2
    email.assert_called_once()
    assert email.call_args.kwargs["to_email"] == row.requester.email
    assert row.resolution_note in email.call_args.kwargs["text_body"]
    for call in send.call_args_list:
        assert call.args[0] == row.makerspace
        assert status in call.args[1]
        assert row.requester.email not in call.args[1]
        assert row.resolution_note not in call.args[1]
        assert "private-bot-token" not in call.args[1]
    logs = list(NotificationDeliveryLog.objects.filter(makerspace=row.makerspace))
    assert len(logs) == 2
    assert all(log.event == EVENT and log.feature == FEATURE for log in logs)
    assert all(log.payload["source_kind"] == "apiclients.request" for log in logs)
    assert all(log.payload["source_id"] == str(row.pk) and log.payload["p2_intent"] for log in logs)
    envelope = NotificationEnvelope.objects.get(recipient=row.requester)
    assert envelope.source_kind == "apiclients.request" and envelope.source_id == str(row.pk)
    assert envelope.processed_at and envelope.deliveries.get(channel="email").state == "sent"


def test_resolution_channel_mutes_stop_both_email_and_telegram(monkeypatch, deliver_resolution):
    row = resolved_request()
    for channel in ("email", "telegram"):
        NotificationPreference.objects.create(
            makerspace=row.makerspace, feature=FEATURE, channel=channel, enabled=False,
        )
    email, send, reserve = Mock(), Mock(), Mock()
    monkeypatch.setattr(dispatch, "dispatch_email", email)
    monkeypatch.setattr(telegram, "send_message", send)
    monkeypatch.setattr(limits, "reserve_notification_quota", reserve)
    deliver_resolution(row)
    assert delivery_counts(row.makerspace, "sent") == delivery_counts(row.makerspace, "failed") == {}
    email.assert_not_called()
    send.assert_not_called()
    reserve.assert_not_called()
    assert not NotificationDeliveryLog.objects.exists()


@pytest.mark.parametrize("blocked", ["module", "quota"])
def test_resolution_obeys_module_and_quota_blocks(monkeypatch, blocked, deliver_resolution):
    row = resolved_request()
    mute_email(row.makerspace)
    if blocked == "module":
        disable_module(row.makerspace, "telegram")
        row.makerspace.refresh_from_db()
    reserve, send = Mock(return_value=False), Mock(return_value=True)
    monkeypatch.setattr(limits, "reserve_notification_quota", reserve)
    monkeypatch.setattr(telegram, "send_message", send)
    deliver_resolution(row)
    log = NotificationDeliveryLog.objects.get()
    assert log.status == ("skipped" if blocked == "module" else "failed")
    assert delivery_counts(row.makerspace, "sent") == {}
    send.assert_not_called()
    assert reserve.call_count == (0 if blocked == "module" else 1)


def test_staff_master_mute_keeps_requester_email_but_stops_rooms(monkeypatch, deliver_resolution):
    row = resolved_request()
    row.makerspace.staff_notifications_enabled = False
    row.makerspace.save(update_fields=["staff_notifications_enabled"])
    email, send = Mock(return_value=Mock(status=EmailLog.Status.SENT)), Mock()
    monkeypatch.setattr(dispatch, "dispatch_email", email)
    monkeypatch.setattr(telegram, "send_message", send)
    deliver_resolution(row)
    assert delivery_counts(row.makerspace, "sent") == {"email": 1}
    email.assert_called_once()
    send.assert_not_called()


def test_resolution_provider_failure_is_logged_and_does_not_escape(monkeypatch, caplog, deliver_resolution):
    row = resolved_request()
    mute_email(row.makerspace)
    monkeypatch.setattr(telegram, "send_message", Mock(side_effect=RuntimeError("private-bot-token")))
    deliver_resolution(row)
    log = NotificationDeliveryLog.objects.get()
    assert delivery_counts(row.makerspace, "failed") == {"telegram": 1}
    assert log.status == "failed"
    assert "private-bot-token" not in log.error + caplog.text


def test_resolution_rollback_sends_nothing(monkeypatch, django_capture_on_commit_callbacks):
    row = resolved_request()
    send, email = Mock(), Mock()
    monkeypatch.setattr(telegram, "send_message", send)
    monkeypatch.setattr(dispatch, "dispatch_email", email)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                notify_api_key_request_resolved(row)
                raise RuntimeError("rollback")
    assert callbacks == []
    assert not NotificationEnvelope.objects.exists()
    assert not NotificationDeliveryLog.objects.exists()
    email.assert_not_called()
    send.assert_not_called()


def test_api_access_catalog_preserves_defaults_and_can_be_muted_via_scoped_api():
    space = make_space("api-resolution-rules")
    actor = make_member("api-resolution-manager", space)
    assert FEATURE_EVENTS[FEATURE] == (EVENT, "subdomain_request_resolved", "email.failed", "scheduled_report",
                                      "space_restore_completed", "space_restore_failed", "emergency_rekey_started",
                                      "emergency_rekey_completed", "emergency_rekey_failed", "selfhost_move_status")
    assert DEFAULT_CHANNEL_STATE[FEATURE] == {
        channel: channel in {"email", "telegram", "in_app"} for channel in NotificationChannel.values
    }
    url = reverse("admin-notification-rules", kwargs={"makerspace_id": space.pk})
    response = authenticated_client(actor).patch(url, {
        "preferences": [{"feature": FEATURE, "channel": "telegram", "enabled": False}],
    }, format="json")
    assert response.status_code == 200
    assert NotificationPreference.objects.get(makerspace=space, feature=FEATURE).enabled is False
    assert AuditLog.objects.filter(makerspace=space, action="notification.preferences_updated").exists()
    other = make_member("api-resolution-other", make_space("api-resolution-other"))
    assert authenticated_client(other).patch(url, {
        "preferences": [{"feature": FEATURE, "channel": "telegram", "enabled": True}],
    }, format="json").status_code == 404
