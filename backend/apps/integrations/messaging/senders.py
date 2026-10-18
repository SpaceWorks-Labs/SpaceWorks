"""Unique sender claims and callback credentials retained for fourteen days."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Max, Q, Value, When
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.integrations.models import MessagingSenderCredential, MessagingSenderIdentity
from .locks import advisory_lock


class SenderInUse(APIException):
    status_code = 409
    default_code = "sender_in_use"
    default_detail = {"code": "sender_in_use", "detail": "This sender is reserved by another configuration."}


@transaction.atomic
def reserve_sender(*, sender_key, channel, owner, makerspace=None, webhook_secret="", verify_token="", force_rotate=False):
    """Claim/reactivate ownership and rotate only if callback credentials changed."""
    advisory_lock("messaging-settings")
    if owner == "makerspace" and channel == "sms":
        from apps.integrations.models import PlatformSmsSettings
        otp = PlatformSmsSettings.objects.filter(pk=1).first()
        parts = sender_key.split(":", 2)
        if otp and len(parts) == 3 and ((parts[1] and parts[1] == otp.account_sid) or
                                       (parts[2] and parts[2] == otp.from_number)):
            raise SenderInUse()
    try:
        with transaction.atomic():
            identity, _ = MessagingSenderIdentity.objects.get_or_create(
                sender_key=sender_key, defaults={"channel": channel, "owner": owner, "makerspace": makerspace,
                    "tenant_reference": getattr(makerspace, "pk", None)},
            )
    except IntegrityError as exc:
        raise SenderInUse() from exc
    identity = MessagingSenderIdentity.objects.select_for_update().get(pk=identity.pk)
    now = timezone.now()
    if identity.owner != owner or identity.makerspace_id != getattr(makerspace, "pk", None) or identity.channel != channel:
        from apps.integrations.models_cutover import NotificationIngress
        if NotificationIngress.objects.filter(sender_key=sender_key).exclude(state="processed").exists():
            raise SenderInUse()
        if (identity.active or not identity.retired_at or identity.retired_at > now - timedelta(days=14)
            or identity.owner == "platform_otp" or identity.channel != channel):
            raise SenderInUse()
        # After the callback overlap expires the physical sender may be reassigned.
        # Wipe the old owner's verification material before transferring reservation.
        identity.credentials.filter(wiped_at__isnull=True).update(webhook_secret="", verify_token="", wiped_at=now)
        identity.owner, identity.makerspace = owner, makerspace
        identity.tenant_reference = getattr(makerspace, "pk", None)
    current = identity.credentials.filter(retired_at__isnull=True).first()
    if current and not force_rotate and (current.get_secret("webhook_secret"), current.verify_token) == (webhook_secret, verify_token):
        pass
    else:
        identity.credentials.filter(retired_at__isnull=True).update(retired_at=now)
        version = (identity.credentials.aggregate(n=Max("version"))["n"] or 0) + 1
        credential = MessagingSenderCredential(identity=identity, version=version, verify_token=verify_token)
        credential.set_secret("webhook_secret", webhook_secret)
        credential.save()
    identity.active, identity.retired_at = True, None
    identity.save(update_fields=["owner", "makerspace", "tenant_reference", "active", "retired_at"])
    return identity


@transaction.atomic
def retire_sender(identity):
    advisory_lock("messaging-settings")
    now = timezone.now()
    MessagingSenderIdentity.objects.filter(pk=identity.pk, active=True).update(active=False, retired_at=now)
    MessagingSenderCredential.objects.filter(identity=identity, retired_at__isnull=True).update(retired_at=now)


def callback_credentials(*, channel, owner, makerspace_id=None):
    """Active credentials first, then retired versions within the overlap window."""
    cutoff = timezone.now() - timedelta(days=14)
    return MessagingSenderCredential.objects.filter(
        identity__channel=channel, identity__owner=owner,
        wiped_at__isnull=True,
    ).filter(Q(identity__makerspace_id=makerspace_id) | Q(identity__makerspace_id=None, identity__tenant_reference=makerspace_id)
    ).filter(Q(retired_at__isnull=True) | Q(retired_at__gte=cutoff)).select_related("identity").annotate(verification_order=Case(
        When(retired_at__isnull=True, identity__active=True, then=Value(0)),
        default=Value(1), output_field=IntegerField(),
    )).order_by("verification_order", "-version")


@transaction.atomic
def wipe_retired_credentials():
    cutoff = timezone.now() - timedelta(days=14)
    from apps.integrations.models_cutover import NotificationIngress
    pending_senders = NotificationIngress.objects.exclude(state="processed").values("sender_key")
    count = MessagingSenderCredential.objects.filter(retired_at__lt=cutoff, wiped_at__isnull=True).exclude(
        identity__sender_key__in=pending_senders).update(
        webhook_secret="", verify_token="", wiped_at=timezone.now(),
    )

    if count:
        from apps.audit.services import record
        record(None, "messaging.retired_credentials_wiped", meta={"fields": ["webhook_secret", "verify_token", "wiped_at"], "count": count})
    return count
