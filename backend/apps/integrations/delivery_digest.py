"""Rebuild a queued summary from its durable source rows on every SMTP attempt."""

from apps.notifications.preferences import STREAM_FEATURES

from .delivery_sources import DeliverySource, digestible, prepare, register
from .delivery_content import content, render


def prepare_digest(log):
    from .models import EmailLog
    from .reminders_deferred import _allowed
    ids = log.source_metadata.get("entries", [])
    if not isinstance(ids, list) or len(ids) > 200 or any(type(pk) is not int for pk in ids):
        return False
    bodies = []
    for mail in EmailLog.objects.filter(pk__in=ids, makerspace_id=log.makerspace_id,
                                       recipient_id=log.recipient_id).order_by("pk"):
        family = mail.feature or STREAM_FEATURES.get(mail.stream, mail.stream)
        if (family != log.feature or mail.error != "included_in_daily_digest" or not digestible(mail)
                or not prepare(mail) or not _allowed(mail, log.makerspace)):
            continue
        rendered = content(mail)
        bodies.append(f"{rendered.subject}\n{rendered.text_body}")
    render(log, subject=log.subject, text_body="\n\n".join(bodies))
    return bool(bodies)


def register_digest():
    register("notification_digest", DeliverySource(prepare_digest, digestible=False))
