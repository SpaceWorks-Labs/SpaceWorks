"""Keep legacy EmailLog retries attached to the personal envelope's live authority."""
from .models_contract import NotificationDelivery


def prepare(log):
    from .notification_delivery import SUCCESS
    from .notification_resolution import eligible, resolve
    from .notification_sources import render
    from .delivery_content import render as render_email
    row = NotificationDelivery.objects.filter(pk=log.source_metadata.get("delivery_id"),
        envelope_id=log.source_id, makerspace_id=log.makerspace_id,
        envelope__recipient_id=log.recipient_id, channel="email", state="retrying").first()
    if row is None or not eligible(row.envelope):
        return False
    others = row.envelope.deliveries.exclude(channel="email")
    fallback = (others.exists() and not others.filter(state__in=SUCCESS).exists()
                and not others.filter(state="retrying").exists())
    if not any(target.channel == "email" for target in resolve(row.envelope, fallback=fallback)):
        return False
    content = render(row.envelope)
    render_email(log, to_email=row.envelope.recipient.email, subject=content.get("subject", "Space Works"),
                 text_body=content.get("text", ""), html_body=content.get("html", ""))
    return True


def retry(log, actor):
    from rest_framework.exceptions import ValidationError
    raise ValidationError({"delivery": "Personal deliveries use the envelope retry budget."})


def register_email_source():
    from .delivery_sources import DeliverySource, register
    register("notification.envelope", DeliverySource(prepare, digestible=False, retry=retry))
