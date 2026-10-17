"""Explicit per-tenant consent, serialized with phone changes and account deletion."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.services import record
from apps.integrations.models import MessagingConsent, MessagingRecipientCorrelation
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.tenant_migration.gate_runtime import tenant_write
from .locks import lock_whatsapp_sender
from .protections import lock_suppression_key, recipient_hash, suppressed, suppression_rows
from .resolver import resolve_sender


class VerifiedPhoneRequired(APIException):
    status_code = 409
    default_detail = {"code": "phone_unverified", "detail": "Verify your phone before opting in."}


class _SenderChanged(Exception):
    pass


def member_space(user, makerspace_id):
    if not user.is_active or user.is_tenant_dump_stub:
        raise NotFound()
    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not is_servable(space) or not rbac.scope_notification_policy(
        MakerspaceMembership.objects.all(), makerspace_id=space.pk,
    ).filter(user=user, status="active").exists():
        raise NotFound()
    return space


def live_consent(makerspace, user, channel):
    row = MessagingConsent.objects.filter(makerspace=makerspace, user=user, channel=channel).order_by("-id").first()
    return bool(row and row.action == "opted_in" and user.phone_e164 and user.phone_verified_at
                and row.phone_e164 == user.phone_e164 and row.phone_verified_at == user.phone_verified_at)


def member_payload(space, user):
    phone = user.phone_e164 or ""
    result = {}
    for channel in ("sms", "whatsapp"):
        sender = resolve_sender(space, channel)
        result[channel] = {
            "available": module_enabled(space, channel) and sender is not None,
            "consented": live_consent(space, user, channel),
            "phone_verified": bool(phone and user.phone_verified_at),
            "phone_masked": "***" + phone[-4:] if phone else "",
            "suppressed": bool(sender and phone and suppressed(channel, sender.sender_key, recipient_hash("phone", phone))),
        }
    return result


def grant_consent(*, user, makerspace_id, channel, action, source="member_settings"):
    if channel not in {"sms", "whatsapp"} or action not in MessagingConsent.Action.values:
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Invalid messaging channel or consent action.")
    # Sender can rotate while acquiring locks: restart before taking a new sender lock.
    for _ in range(3):
        space = member_space(user, makerspace_id)
        sender = resolve_sender(space, channel)
        try:
            return _grant(user, space, channel, action, source, sender)
        except _SenderChanged:
            continue
    error = APIException({"code": "sender_changed", "detail": "Sender configuration changed. Try again."})
    error.status_code = 503
    raise error


@transaction.atomic
def _grant(user, space, channel, action, source, sender):
    if sender and channel == "whatsapp":
        lock_whatsapp_sender(sender.sender_key)
    # Lock order: sender advisory lock, source gate, tenant, User, suppression rows.
    with tenant_write(space.pk):
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        user = User.objects.select_for_update().get(pk=user.pk)
        member_space(user, space.pk)
        current = resolve_sender(space, channel)
        if getattr(current, "sender_key", None) != getattr(sender, "sender_key", None):
            raise _SenderChanged()
        if action == "opted_in" and not (user.phone_e164 and user.phone_verified_at):
            raise VerifiedPhoneRequired()
        lifted = []
        if action == "opted_in" and sender:
            phone_hash = recipient_hash("phone", user.phone_e164)
            lock_suppression_key(channel, sender.sender_key, phone_hash)
            rows = suppression_rows(channel, sender.sender_key, phone_hash).select_for_update().order_by("pk")
            lifted = list(rows.values_list("pk", flat=True))
            rows.update(lifted_at=timezone.now())
            if channel == "whatsapp":
                reset = MessagingRecipientCorrelation.objects.filter(channel=channel, sender_key=sender.sender_key,
                    phone_hash=phone_hash, state="blocked").delete()[0]
                if reset:
                    record(user, "messaging.correlation_reset", makerspace=space, meta={"fields": ["state"]})
        row = MessagingConsent.objects.create(makerspace=space, user=user, channel=channel, action=action,
            source=source, phone_e164=user.phone_e164 or "", phone_verified_at=user.phone_verified_at,
            lifted_suppression_id=lifted)
        record(user, "messaging.consent_recorded", makerspace=space, target=row,
               meta={"fields": ["channel", "action", "source", "lifted_suppression_id"]})
        return member_payload(space, user)
