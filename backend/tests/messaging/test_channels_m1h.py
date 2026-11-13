from unittest.mock import patch

import pytest

from apps.integrations.dispatch_channels import dispatch_channel
from apps.integrations.notification_catalog import DEFAULT_CHANNEL_STATE
from apps.integrations.notification_enums import CHANNEL_MODULE_KEYS, ChatNotificationChannel, NotificationChannel
from apps.notifications.preferences import PERSONAL_CHANNELS, channel_available


@pytest.mark.django_db
@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_addressed_channels_have_their_own_module_gate(space, channel):
    with patch("apps.integrations.recipients.feature_available", return_value=True), \
         patch("apps.notifications.preferences.is_notification_enabled", return_value=True), \
         patch("apps.notifications.preferences.module_enabled", return_value=True) as module, \
         patch("apps.notifications.preferences.feature_enabled", return_value=False) as push:
        assert channel_available(space, "bookings", channel)
    module.assert_called_once_with(space, channel)
    push.assert_not_called()
    assert channel in PERSONAL_CHANNELS and CHANNEL_MODULE_KEYS[channel] == channel
    assert channel in NotificationChannel.values and channel not in ChatNotificationChannel.values
    assert all(cells[channel] is False for cells in DEFAULT_CHANNEL_STATE.values())
    with pytest.raises(ValueError):
        dispatch_channel(makerspace=space, channel=channel, feature="bookings", event="created", text_body="text")
