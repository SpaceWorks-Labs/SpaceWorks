"""Optional preference stores constrain consent; removing the inbox cannot grant authority."""
from django.apps import apps


def selection_model():
    try:
        return apps.get_model("notifications", "NotificationPreference")
    except LookupError:
        return None


def personal_enabled(makerspace, user_id, feature, channel, *, stream="", event=""):
    from apps.notifications.preferences import mandatory_email
    if channel == "email" and mandatory_email(stream, event):
        return True
    if not apps.is_installed("apps.notifications"):
        from .notification_saved_policy import opted_out
        return not opted_out(makerspace, user_id, feature, channel)
    from apps.notifications.preferences import personal_enabled as allowed
    return allowed(makerspace, user_id, feature, channel, stream=stream, event=event)


def preference_for(space, user, feature):
    model = selection_model()
    if model:
        from apps.accounts import rbac
        return rbac.scope_notification_policy(model.objects.all(), makerspace_id=space.pk).filter(
            user=user, category=feature).first()
    from .notification_saved_policy import saved_selection
    return saved_selection(space, user, feature)


def consented_channels(space, user):
    from .messaging.consent import live_consent
    from .models_endpoints import NotificationEndpoint
    from .notification_resolution import endpoint_current
    result = ["sms"] if live_consent(space, user, "sms") else []
    endpoint = NotificationEndpoint.objects.filter(makerspace=space, user=user, channel="whatsapp", revoked_at=None).first()
    if endpoint_current(endpoint):
        from .models_messaging_consent import MessagingConsent
        latest = MessagingConsent.objects.filter(makerspace=space, user=user, channel="whatsapp").order_by("-pk").first()
        if latest is None or latest.action == "opted_in":
            result.append("whatsapp")
    return result
