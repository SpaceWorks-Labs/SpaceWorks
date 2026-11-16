"""Channel-only purge preserves shared phone/alias protection and the other rail."""
from contextlib import contextmanager

from django.apps import apps
from django.db import connection, transaction

from apps.integrations.models import (
    MakerspaceMessagingSettings, MessagingConsent, MessagingDelivery, MessagingSenderIdentity,
    MessagingWebhookEvent, WhatsAppTemplateBinding,
)
from .locks import advisory_lock
from apps.integrations.notification_cutover import guarded


@contextmanager
def consent_purge():
    """The existing immutable-history DELETE hatch, never an UPDATE permission."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.allow_immutable_delete', true)")
        previous = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.allow_immutable_delete', 'on', true)")
        try:
            yield
        finally:
            cursor.execute("SELECT set_config('app.allow_immutable_delete', %s, true)", [previous])


@guarded(mutation=True)
@transaction.atomic
def purge_channel(makerspace, channel):
    if channel not in {"sms", "whatsapp"}:
        raise ValueError("Unsupported addressed channel.")
    advisory_lock("messaging-settings")
    from apps.integrations.notification_privacy import prepare_channel_purge
    prepare_channel_purge(makerspace, channel)
    counts = {}
    with consent_purge():
        counts["messaging_consents"] = MessagingConsent.objects.filter(makerspace=makerspace, channel=channel).delete()[0]
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.models_endpoints import ChannelConfiguration
    counts["canonical_deliveries"] = NotificationDelivery.objects.filter(makerspace=makerspace, channel=channel).delete()[0]
    counts["channel_configurations"] = ChannelConfiguration.objects.filter(makerspace=makerspace, channel=channel).delete()[0]
    counts["messaging_deliveries"] = MessagingDelivery.objects.filter(makerspace=makerspace, channel=channel).delete()[0]
    MessagingWebhookEvent.objects.filter(makerspace=makerspace, channel=channel).delete()
    values = ({"sms_account_sid": "", "sms_auth_token": "", "sms_from_number": "", "sms_sender_key": None}
              if channel == "sms" else {"whatsapp_phone_number_id": "", "whatsapp_business_account_id": "",
              "whatsapp_access_token": "", "whatsapp_app_secret": "", "whatsapp_webhook_verify_token": "", "whatsapp_sender_key": None})
    MakerspaceMessagingSettings.objects.filter(makerspace=makerspace).update(**values)
    if channel == "whatsapp":
        WhatsAppTemplateBinding.objects.filter(makerspace=makerspace).delete()
    return counts


def sms_delete(makerspace, cursor):
    return purge_channel(makerspace, "sms")


def whatsapp_delete(makerspace, cursor):
    return purge_channel(makerspace, "whatsapp")


@guarded(mutation=True)
def purge_user(user, makerspace_id):
    if apps.is_installed("apps.notifications"):
        from apps.notifications.privacy import scrub_account as scrub_push
        scrub_push(user, makerspace_id, purge=True)
    from apps.integrations.notification_privacy import scrub_account
    scrub_account(user, makerspace_id)
    with consent_purge():
        MessagingConsent.objects.filter(user=user, makerspace_id=makerspace_id).delete()
    MessagingDelivery.objects.filter(user=user, makerspace_id=makerspace_id).delete()
    from apps.integrations.models_endpoints import NotificationEndpoint, NotificationEndpointChallenge
    NotificationEndpointChallenge.objects.filter(user=user, makerspace_id=makerspace_id).delete()
    NotificationEndpoint.objects.filter(user=user, makerspace_id=makerspace_id).delete()


@guarded(mutation=True)
def archive_consents(user, spaces):
    from apps.audit.services import record
    from .consent import live_consent
    for space in spaces:
        for channel in ("sms", "whatsapp"):
            if live_consent(space, user, channel):
                row = MessagingConsent.objects.create(makerspace=space, user=user, channel=channel,
                    action="opted_out", source="account_archive", phone_e164=user.phone_e164 or "",
                    phone_verified_at=user.phone_verified_at)
                record(user, "messaging.consent_archived", makerspace=space, target=row, meta={"fields": ["action", "source"]})
        from apps.integrations.notification_privacy import scrub_account
        scrub_account(user, space.pk)
