"""Real database fixtures shared by the pipeline/webhook regression tests."""
from types import SimpleNamespace
from unittest.mock import patch

from apps.hardware_requests.models import HardwareRequest
from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.dispatch import enqueue_addressed_messages
from apps.integrations.messaging.resolver import resolve_sender
from apps.integrations.messaging.settings_service import sync_platform_sms, sync_platform_whatsapp
from apps.integrations.models import NotificationPreference, PlatformSmsSettings, PlatformWhatsAppSettings, WhatsAppTemplateBinding
from apps.integrations.notify import LifecyclePayload
from apps.notifications.inbox import InboxDelivery


def setup_pipeline(space, member):
    sms = PlatformSmsSettings(account_sid="AC" + "a" * 32, from_number="+14155550001",
        notifications_from_number="+14155550002", notifications_enabled=True)
    sms.set_auth_token("twilio-secret")
    sync_platform_sms(sms)
    wa = PlatformWhatsAppSettings(is_enabled=True, phone_number_id="123", business_account_id="456")
    wa.set_secret("access_token", "meta-access")
    wa.set_secret("app_secret", "meta-secret")
    sync_platform_whatsapp(wa)
    for channel in ("sms", "whatsapp"):
        NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests", channel=channel,
                                                      defaults={"enabled": True})
        grant_consent(user=member, makerspace_id=space.pk, channel=channel, action="opted_in")
    for audience in ("member", "staff"):
        WhatsAppTemplateBinding.objects.create(makerspace=None, feature="hardware_requests", event="accepted",
            audience=audience, business_account_id="456", template_name=f"loan_{audience}", language="en", parameters=[])
    request = HardwareRequest.objects.create(makerspace=space, requester=member, requester_username=member.username)
    payload = LifecyclePayload(text="Staff wording", data={"request_id": request.pk},
        inbox=(InboxDelivery(member.pk, "Your request", "Member wording"),))

    def enqueue(channel="sms", key="edge-1", tenant=None):
        with patch("apps.integrations.messaging.dispatch.schedule_delivery"):
            rows = enqueue_addressed_messages(tenant or space, feature="hardware_requests", event="accepted",
                                              event_key=key, payload=payload, channels=(channel,))
        return next(row for row in rows if row.user_id == member.pk)

    return SimpleNamespace(space=space, member=member, request=request, payload=payload, enqueue=enqueue,
                           sms=resolve_sender(space, "sms"), wa=resolve_sender(space, "whatsapp"))
