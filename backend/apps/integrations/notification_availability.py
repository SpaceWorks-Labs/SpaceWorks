"""The tenant's selectable media, independent of a person's saved opt-outs."""
from .models_endpoints import ChannelConfiguration
from .notification_enums import NotificationChannel


def available_channels(space, feature):
    from .notification_catalog import is_notification_enabled
    from .recipients import category_available
    from .dispatch_channels import channel_module_blocks
    from apps.makerspaces.platform import feature_enabled, module_enabled
    if not category_available(space, feature):
        return []
    configs = {row.channel: row for row in ChannelConfiguration.objects.filter(makerspace=space)}
    result = []
    for channel in NotificationChannel.values:
        if channel == "webhook" or not is_notification_enabled(space, feature, channel):
            continue
        config = configs.get(channel)
        if config and not (config.enabled and config.personal_enabled):
            continue
        if channel == "email":
            allowed = module_enabled(space, "email")
        elif channel == "in_app":
            allowed = feature_enabled(space, "notifications.member_inbox")
        elif channel == "native_push":
            allowed = feature_enabled(space, "mobile.push")
        elif channel in {"sms", "whatsapp"}:
            from .messaging.resolver import resolve_sender
            allowed = bool(config and module_enabled(space, channel) and resolve_sender(space, channel))
        else:
            allowed = bool(config and not channel_module_blocks(space, channel))
        if allowed:
            result.append(channel)
    return result
