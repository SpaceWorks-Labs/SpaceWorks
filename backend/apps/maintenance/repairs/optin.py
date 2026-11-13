"""The one-time opt-in link that records a technician's chat consent (#128 C-4).

Staff create a link (valid 7 days; only its digest is stored) and it is emailed to the
technician. Opening it, the technician agrees to WhatsApp and/or SMS on the number the
space holds for them; sending `/start <code>` to the space's Telegram bot records the
private chat to use. Each consent is timestamped on the contact and audited. Email needs
no opt-in: it is always the first channel.
"""

from django.utils.translation import gettext
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

LIFETIME = timedelta(days=7)


def digest(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


@transaction.atomic
def create_link(actor, contact):
    from apps.makerspaces.website_directory import public_url
    from . import services_contacts
    services_contacts._require(actor, contact.makerspace_id)
    if contact.is_archived:
        raise ValidationError({"detail": gettext("This technician is archived.")})
    token = secrets.token_urlsafe(24)
    contact.opt_in_digest, contact.opt_in_expires_at = digest(token), timezone.now() + LIFETIME
    contact.save(update_fields=["opt_in_digest", "opt_in_expires_at", "updated_at"])
    url = public_url(contact.makerspace, "technician-opt-in", token)
    emailed = _email_link(contact, url, token)
    audit.record(actor, "technician.opt_in_link_created", makerspace=contact.makerspace, target=contact,
                 meta={"contact_id": contact.pk, "emailed": emailed})
    return {"url": url, "telegram_start": f"/start {token}", "expires_at": contact.opt_in_expires_at,
            "emailed": emailed}


def _email_link(contact, url, token):
    from .notify import _email
    if not contact.email:
        return False
    body = (f"{contact.makerspace.name} would like to send you repair requests.\n\n"
            f"Open this link to choose WhatsApp or SMS: {url}\n"
            f"For Telegram, send this message to the space's Telegram bot: /start {token}\n\n"
            "The link works for 7 days. You can always be reached by email.")
    return bool(_email(contact.makerspace, contact.email, "Get repair requests by chat", body,
                       event="technician_opt_in", feature="maintenance"))


def contact_for_token(token, *, lock=False):
    from apps.maintenance.models import TechnicianContact
    rows = TechnicianContact.objects.select_related("makerspace")
    if lock:
        rows = rows.select_for_update(of=("self",))
    contact = rows.filter(opt_in_digest=digest(token), opt_in_expires_at__gt=timezone.now(),
                          is_archived=False).first() if token else None
    if contact is None:
        raise NotFound({"detail": gettext("This opt-in link is invalid or has expired."), "code": "opt_in_invalid"})
    if lock:
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(contact.makerspace_id)
    return contact


@transaction.atomic
def accept(token, channels):
    """The technician's own consent from the web page: WhatsApp and/or SMS."""
    contact = contact_for_token(token, lock=True)
    channels = set(channels or [])
    if not channels or channels - {"whatsapp", "sms"}:
        raise ValidationError({"channels": gettext("Choose WhatsApp, SMS or both.")})
    if not contact.phone:
        raise ValidationError({"channels": gettext("The space has no phone number for you yet.")})
    now = timezone.now()
    for channel in sorted(channels):
        setattr(contact, f"{channel}_opted_in_at", now)
    contact.channels = sorted(set(contact.channels or ["email"]) | channels | {"email"})
    contact.save()
    audit.record(None, "technician.opted_in", makerspace=contact.makerspace, target=contact,
                 meta={"contact_id": contact.pk, "channels": sorted(channels)})
    return contact


def telegram_start(code, chat_id):
    """Called from the Telegram webhook's private `/start <code>` path after the secret
    header was verified; a code that is not a live opt-in link is ignored."""
    try:
        with transaction.atomic():
            contact = contact_for_token(code, lock=True)
            contact.telegram_chat_id, contact.telegram_opted_in_at = str(chat_id), timezone.now()
            contact.channels = sorted(set(contact.channels or ["email"]) | {"email", "telegram"})
            contact.save()
            audit.record(None, "technician.opted_in", makerspace=contact.makerspace, target=contact,
                         meta={"contact_id": contact.pk, "channels": ["telegram"]})
            return True
    except NotFound:
        return False
