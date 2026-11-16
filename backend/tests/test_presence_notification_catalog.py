"""Presence is a selectable personal category with closed transport defaults."""

from importlib import import_module

from django.apps import apps

from apps.integrations.models import NotificationChannel, NotificationFeature
from apps.integrations.notification_catalog import DEFAULT_CHANNEL_STATE, FEATURE_EVENTS


def test_presence_feature_has_explicit_personal_only_defaults():
    feature = NotificationFeature.PRESENCE
    assert feature == "presence"
    assert FEATURE_EVENTS[feature] == ("expired",)
    defaults = DEFAULT_CHANNEL_STATE[feature]
    assert set(defaults) == set(NotificationChannel.values)
    assert {channel for channel, enabled in defaults.items() if enabled} == {
        "in_app", "native_push",
    }


def test_presence_feature_choices_match_the_frozen_migration():
    migration = import_module("apps.integrations.migrations.0037_presence_notification_feature")
    assert migration.Migration.dependencies == [("integrations", "0036_notification_pii_fences")]
    assert migration.FEATURE_CHOICES == NotificationFeature.choices
    assert {operation.model_name for operation in migration.Migration.operations} == {
        "chattemplate", "notificationdeliverylog", "notificationpreference", "notificationrecipient",
    }
    for name in ("ChatTemplate", "NotificationDeliveryLog", "NotificationPreference", "NotificationRecipient"):
        assert apps.get_model("integrations", name)._meta.get_field("feature").choices == migration.FEATURE_CHOICES
