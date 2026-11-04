"""Equipment email policy/content hooks used by shared resolution and transport.

Chat keeps the credential-free body persisted on the personal envelope.
"""
from apps.accounts import rbac
from apps.integrations.notification_rules import is_requester_muted
from apps.notifications.preferences import mandatory_email
from .models import HardwareRequest


def source_ready(envelope):
    """Keep chat independent once the resolver owns email-specific refusals."""
    if allowed(envelope) is not False:
        return True
    from apps.integrations import notification_resolution
    # Once installed, the channel resolver refuses email while allowing the
    # recipient's separately selected chat. Until then, refuse the whole intent.
    return getattr(notification_resolution, "EQUIPMENT_EMAIL_POLICY", None) is allowed


def allowed(envelope):
    """Return None for another lane's source; bool for equipment owner mail."""
    if envelope.audience != "requester":
        return None
    if envelope.source_kind == "hardware.request":
        from .notifications_p2_requests import KEYS
        if not mandatory_email(envelope.stream, envelope.event) and is_requester_muted(
            envelope.makerspace, "hardware", KEYS[envelope.event],
        ):
            return False
        row = rbac.scope_notification_policy(HardwareRequest.objects.all(),
            makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id,
            requester_id=envelope.recipient_id).first()
        return bool(row and row.requester_contact_email and row.requester_contact_verified)
    if envelope.source_kind == "machines.service":
        return not is_requester_muted(envelope.makerspace, "printing", envelope.event)
    return None


def proven_address(envelope):
    """An existing contact proof can prove the SAME owner's mailbox, never another."""
    if envelope.source_kind not in {"hardware.request", "hardware.loan_reminder"} or envelope.audience != "requester":
        return False
    row = rbac.scope_notification_policy(HardwareRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id,
        requester_id=envelope.recipient_id, requester_contact_verified=True).first()
    # Scoped PII is ciphertext in SQL; the model accessor decrypts this owned row.
    return bool(row and row.requester_contact_email == envelope.recipient.email)


def render_email(envelope, fallback):
    """Rebuild legacy tracking mail only at the email transport, including retries."""
    if envelope.source_kind != "machines.service" or envelope.audience != "requester":
        return fallback
    from apps.machines.models import MachineServiceRequest
    from apps.machines.service_printing_emails import _is_printer_request, _requester_render, REQUESTER_EVENTS
    from .notifications_p2 import content
    row = rbac.scope_notification_policy(MachineServiceRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related(
        "queue__machine_type", "bucket__machine__machine_type", "requester").filter(pk=envelope.source_id).first()
    # Failed/collected/reprinted are new requester messages and have no legacy
    # requester template; keep their safe generic content.
    if row is None or not _is_printer_request(row) or envelope.event not in REQUESTER_EVENTS - {"failed", "collected", "reprinted"}:
        return fallback
    _, rendered = _requester_render(envelope.event, row)
    return content(rendered) if rendered else fallback
