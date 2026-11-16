from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models_contract import NotificationEnvelope, NotificationDelivery
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.makerspaces.models import Makerspace


def space(slug="recon-m"):
    return Makerspace.objects.create(name=slug, slug=slug)


def account(name="recon-member", **kwargs):
    values = {"username": name, "email": name + "@example.test", **kwargs}
    return User.objects.create_user(**values)


def sms_config(makerspace):
    row = ChannelConfiguration(makerspace=makerspace, channel="sms", provider="twilio",
        enabled=True, personal_enabled=True, generation=2, credential_version=2,
        sender_key="twilio:AC" + "a" * 32 + ":+14155550100")
    row.set_credentials({"account_sid": "AC" + "a" * 32, "auth_token": "b" * 32, "from_number": "+14155550100"})
    row.save()
    return row


def delivery(makerspace, user, *, channel="sms", state="retrying", number=1, **kwargs):
    envelope = NotificationEnvelope.objects.create(makerspace=makerspace, recipient=user,
        feature="bookings", event="confirmed", audience="member", source_kind="migration.history",
        source_id=str(number), dedup_key=f"recon:{number}")
    return NotificationDelivery.objects.create(makerspace=makerspace, envelope=envelope,
        channel=channel, target_key=channel, provider="twilio", state=state, **kwargs)
