"""Explicit per-tenant consent, serialized with phone changes and account deletion."""
from django.utils.translation import gettext
from apps.accounts.staff_identity import has_staff_role
from apps.integrations.notification_cutover import guarded
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.accounts.models import User
from apps.audit.services import record
from apps.integrations.models import MessagingConsent, MessagingRecipientCorrelation
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.tenant_migration.gate_runtime import tenant_write
from .locks import lock_whatsapp_sender
from .protections import lock_suppression_key, recipient_hash, suppressed, suppression_rows
from .resolver import resolve_sender
from .ties import has_tenant_tie


class VerifiedPhoneRequired(APIException):
    status_code = 409
    default_detail = {"code": "phone_unverified", "detail": "Verify your phone before opting in."}


class _SenderChanged(Exception):
    pass


def member_space(user, makerspace_id):
    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not is_servable(space):
        raise NotFound()
    # A person consents for a space they belong to, or one where they hold a staff role
    # with live authority. Consent grants no membership, delegation or sending authority.
    allowed = has_tenant_tie(user, space)
    if not allowed and has_staff_role(user, space.pk):
        from apps.accounts import rbac
        allowed = (user.access_status == "active" and user.deletion_requested_at is None
                   and user.account_purged_at is None and bool(rbac.effective_actions(user, space.pk)))
    if not allowed:
        raise NotFound()
    return space


def live_consent(makerspace, user, channel, *, configuration=None):
    from apps.integrations.models_endpoints import ChannelConfiguration
    configuration = configuration or ChannelConfiguration.objects.filter(makerspace=makerspace, channel=channel).first()
    row = MessagingConsent.objects.filter(makerspace=makerspace, user=user, channel=channel).order_by("-id").first()
    if not row or row.action != "opted_in" or configuration is None:
        return False
    from apps.integrations.notification_sender import configuration_sender_key
    try:
        current_sender = configuration_sender_key(configuration)
    except Exception:
        return False
    if row.sender_key != current_sender or row.configuration_generation != configuration.generation:
        return False
    if channel == "whatsapp":
        from apps.integrations.notification_resolution import endpoint_current
        return bool(row.endpoint_id and endpoint_current(row.endpoint) and row.endpoint.user_id == user.pk)
    return bool(user.phone_e164 and user.phone_verified_at and row.phone_e164 == user.phone_e164
        and row.phone_verified_at == user.phone_verified_at)


def member_payload(space, user):
    phone = user.phone_e164 or ""
    result = {}
    for channel in ("sms", "whatsapp"):
        sender = resolve_sender(space, channel)
        consented = live_consent(space, user, channel)
        verified = bool(phone and user.phone_verified_at)
        display_phone = phone
        if channel == "whatsapp":
            from apps.integrations.models_endpoints import NotificationEndpoint
            from apps.integrations.notification_resolution import endpoint_current
            endpoint = NotificationEndpoint.objects.filter(makerspace=space, user=user, channel=channel, revoked_at=None).first()
            latest = MessagingConsent.objects.filter(makerspace=space, user=user, channel=channel).order_by("-pk").first()
            verified = endpoint_current(endpoint)
            consented = bool(verified and (latest is None or latest.action == "opted_in"))
            display_phone = endpoint.destination if endpoint else phone
        result[channel] = {
            "available": module_enabled(space, channel) and sender is not None,
            "consented": consented,
            "phone_verified": verified,
            "phone_masked": "***" + display_phone[-4:] if display_phone else "",
            "suppressed": bool(sender and display_phone and suppressed(channel, sender.sender_key, recipient_hash("phone", display_phone))),
        }
    return result


@guarded(mutation=True)
def grant_consent(*, user, makerspace_id, channel, action, source="member_settings"):
    if channel not in {"sms", "whatsapp"} or action not in MessagingConsent.Action.values:
        from rest_framework.exceptions import ValidationError
        raise ValidationError(gettext("Invalid messaging channel or consent action."))
    # Sender can rotate while acquiring locks: restart before taking a new sender lock.
    for _ in range(3):
        space = member_space(user, makerspace_id)
        sender = resolve_sender(space, channel)
        try:
            return _grant(user, space, channel, action, source, sender)
        except _SenderChanged:
            continue
    error = APIException({"code": "sender_changed", "detail": gettext("Sender configuration changed. Try again.")})
    error.status_code = 503
    raise error


def _grant(user, space, channel, action, source, sender):
    # Lock order: source gate, sender advisory lock, tenant, User, suppression rows.
    with tenant_write(space.pk):
        if sender and channel == "whatsapp":
            lock_whatsapp_sender(sender.sender_key)
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        user = User.objects.select_for_update().get(pk=user.pk)
        member_space(user, space.pk)
        current = resolve_sender(space, channel)
        if getattr(current, "sender_key", None) != getattr(sender, "sender_key", None):
            raise _SenderChanged()
        if channel == "sms" and action == "opted_in" and not (user.phone_e164 and user.phone_verified_at):
            raise VerifiedPhoneRequired()
        from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
        config = ChannelConfiguration.objects.filter(makerspace=space, channel=channel).first()
        endpoint = None
        if action == "opted_in":
            from rest_framework.exceptions import ValidationError
            if config is None or sender is None:
                raise ValidationError({"channel": gettext("Configure a sender before consenting.")})
            if channel == "whatsapp":
                from apps.integrations.notification_resolution import endpoint_current
                endpoint = NotificationEndpoint.objects.filter(configuration=config, user=user, revoked_at=None).first()
                if not endpoint_current(endpoint):
                    raise ValidationError({"channel": gettext("Complete the signed WhatsApp account-link proof first.")})
        if channel == "whatsapp" and action == "opted_out":
            NotificationEndpoint.objects.filter(configuration=config, user=user, revoked_at=None).update(
                revoked_at=timezone.now(), verification_state="revoked")
        lifted = []
        if action == "opted_in" and sender:
            phone_hash = recipient_hash("phone", endpoint.destination if endpoint else user.phone_e164)
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
            lifted_suppression_id=lifted, sender_key=sender.sender_key if sender else "",
            configuration_generation=config.generation if config else 0, endpoint=endpoint)
        record(user, "messaging.consent_recorded", makerspace=space, target=row,
               meta={"fields": ["channel", "action", "source", "lifted_suppression_id"]})
        return member_payload(space, user)
