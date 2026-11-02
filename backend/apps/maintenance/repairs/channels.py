"""One outbound send to one technician over one channel (#128 C-4). Never raises.

Email always (the space's mail, recorded in the email log). Telegram, WhatsApp and SMS
only with that channel's recorded opt-in, only while the space's module for it is on
(SMS needs the `sms` module), and only through the space's own configured sender.
WhatsApp is template-only: it sends the Meta template the space bound to
`maintenance / repair_dispatched / staff`. Every message is plain text -- no buttons,
nothing to act on (chat is never a decision surface).
"""

import logging
from dataclasses import dataclass
from types import SimpleNamespace

from apps.makerspaces.platform import module_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    delivered: bool
    failure_code: str = ""
    message_id: str = ""


def consented(contact, channel):
    if channel == "email":
        return bool(contact.email or getattr(contact.person, "email", ""))
    if channel == "telegram":
        return bool(contact.telegram_opted_in_at and contact.telegram_chat_id)
    return bool(getattr(contact, f"{channel}_opted_in_at") and contact.phone)


def _email(space, contact, subject, text):
    from apps.integrations.dispatch import dispatch_email
    to = contact.email or getattr(contact.person, "email", "")
    log = dispatch_email(to_email=to, subject=subject[:200], text_body=text, makerspace=space, stream="maintenance",
                         event="repair_dispatched", audience="staff", feature="maintenance",
                         recipient_id=contact.person_id)
    if log.status in (log.Status.SKIPPED, log.Status.FAILED):
        return Outcome(False, "email_not_sent", f"email:{log.pk}")
    return Outcome(True, "", f"email:{log.pk}")


def _telegram(space, contact, text):
    from apps.integrations.telegram import TelegramDeliveryError, send_message
    if not module_enabled(space, "telegram"):
        return Outcome(False, "telegram_off")
    try:
        sent = send_message(space, text, SimpleNamespace(telegram_chat_id=contact.telegram_chat_id, pk=None))
    except TelegramDeliveryError:
        return Outcome(False, "telegram_failed")
    return Outcome(True) if sent else Outcome(False, "telegram_unconfigured")


def _messaging(space, contact, channel, text, reference):
    from apps.integrations.messaging.resolver import resolve_sender
    from apps.integrations.messaging.transport import send_message
    if not module_enabled(space, channel):
        return Outcome(False, f"{channel}_off")
    sender = resolve_sender(space, channel)
    if sender is None:
        return Outcome(False, f"{channel}_unconfigured")
    phone = contact.phone.strip()
    if channel == "sms":
        result = send_message(sender, to=phone, delivery_id=reference, body=text[:1500])
    else:
        from apps.integrations.messaging.templates import binding_for
        binding = binding_for(space, sender, "maintenance", "repair_dispatched", "staff")
        if binding is None:
            return Outcome(False, "whatsapp_template_missing")
        values = {"makerspace.name": space.name}
        result = send_message(sender, to=phone.lstrip("+"), delivery_id=reference,
                              template_name=binding.template_name, language=binding.language,
                              parameters=[str(values.get(key, "")) for key in binding.parameters])
    if result.message_id:
        return Outcome(True, "", result.message_id[:255])
    return Outcome(False, (result.error_code or "send_failed")[:64])


def send(space, contact, channel, subject, text, reference):
    try:
        if channel == "email":
            return _email(space, contact, subject, text)
        if channel == "telegram":
            return _telegram(space, contact, text)
        return _messaging(space, contact, channel, text, reference)
    except Exception as exc:  # a provider failure is a recorded failed send, never a 500
        logger.warning("repairs_dispatch_failed", extra={"makerspace_id": space.pk, "channel": channel,
                                                         "error_class": type(exc).__name__})
        return Outcome(False, "send_error")
