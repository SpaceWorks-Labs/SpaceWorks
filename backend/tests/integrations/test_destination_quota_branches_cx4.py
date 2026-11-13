"""Destination tests reserve quota only for a configured endpoint and enqueue after commit."""
from unittest.mock import Mock

import pytest

from apps.integrations import delivery_tests
from apps.integrations.models import NotificationDeliveryLog, NotificationDestination
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("configured,allowed,status,error", [
    (False, True, "failed", "notification_channel_not_configured"),
    (True, False, "failed", "notification_quota_exceeded"),
    (True, True, "pending", ""),
])
def test_destination_configuration_and_quota_have_distinct_terminal_results(
        monkeypatch, django_capture_on_commit_callbacks, configured, allowed, status, error):
    space = make_space("cx4-destination")
    destination = NotificationDestination(makerspace=space, channel="webhook", label="Ops")
    destination.set_webhook_url("https://hooks.example.test/incoming")
    destination.set_signing_secret("cx4-test-secret")
    destination.save()
    foreign = make_space("cx4-destination-foreign")
    reserve, enqueue = Mock(return_value=allowed), Mock()
    monkeypatch.setattr(delivery_tests, "_channel_configured", Mock(return_value=configured))
    monkeypatch.setattr(delivery_tests.limits, "reserve_notification_quota", reserve)
    monkeypatch.setattr(delivery_tests, "_enqueue_notification", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        row = delivery_tests.queue_destination_test(space, destination, "Connection test")
        enqueue.assert_not_called()
    assert (row.status, row.error, row.destination_id, row.makerspace_id) == (status, error, destination.pk, space.pk)
    assert NotificationDeliveryLog.objects.filter(makerspace=foreign).count() == 0
    assert NotificationDeliveryLog.objects.filter(makerspace=space, event="delivery_test").count() == 1
    if configured:
        reserve.assert_called_once_with(space, "webhook")
    else:
        reserve.assert_not_called()
    if configured and allowed:
        enqueue.assert_called_once_with(row.pk)
    else:
        enqueue.assert_not_called()


def test_real_zero_and_one_quota_reservations_never_overspend_or_charge_the_other_tenant(
        monkeypatch, django_capture_on_commit_callbacks):
    from apps.integrations.models import DailyNotificationCounter
    from apps.makerspaces import limits, limits_reservations

    space, foreign = make_space("cx4-quota-real"), make_space("cx4-quota-other")
    destination = NotificationDestination(makerspace=space, channel="webhook", label="Ops")
    destination.set_webhook_url("https://hooks.example.test/incoming")
    destination.set_signing_secret("cx4-quota-secret")
    destination.save()
    monkeypatch.setattr(limits_reservations, "_platform_limit_reached", lambda *_: False)
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    ceiling = {"value": 0}
    monkeypatch.setattr(limits, "resource_limit", lambda *_: ceiling["value"])
    enqueue = Mock()
    monkeypatch.setattr(delivery_tests, "_enqueue_notification", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        zero = delivery_tests.queue_destination_test(space, destination, "Zero cap")
    assert (zero.status, zero.error) == ("failed", "notification_quota_exceeded")
    assert DailyNotificationCounter.objects.get(makerspace=space, channel="webhook").count == 0
    enqueue.assert_not_called()
    ceiling["value"] = 1
    with django_capture_on_commit_callbacks(execute=True):
        accepted = delivery_tests.queue_destination_test(space, destination, "One allowed")
        refused = delivery_tests.queue_destination_test(space, destination, "No more")
    assert (accepted.status, accepted.error) == ("pending", "")
    assert (refused.status, refused.error) == ("failed", "notification_quota_exceeded")
    enqueue.assert_called_once_with(accepted.pk)
    assert DailyNotificationCounter.objects.get(makerspace=space, channel="webhook").count == 1
    assert DailyNotificationCounter.objects.filter(makerspace=foreign).count() == 0
