"""Subject-neutral personal envelopes and F's certificate document source adapter."""

from apps.events.models_certificates import EventAttendanceCertificate
from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable


def certificate_envelope(certificate, event_name):
    from apps.events.notification_envelopes import CERTIFICATE_COPY
    from apps.notifications.inbox import eligible_owner
    event = certificate.event
    space = event.makerspace
    if certificate.registration_id:
        space = certificate.registration.registered_via_makerspace or space
    if not certificate.recipient_member_id or not eligible_owner(space, certificate.recipient_member_id):
        return None
    subject, text = CERTIFICATE_COPY[event_name]
    return emit(makerspace=space, recipient=certificate.recipient_member, feature="events", stream="events",
                event=event_name, audience="requester", source_kind="events.certificate",
                source_id=str(certificate.pk), revision=str(certificate.revision), subject=certificate,
                dedup_key=f"ev:certificate:{certificate.pk}:{certificate.revision}:{event_name}",
                context={"event_id": event.pk, "certificate_id": certificate.pk},
                rendered={"subject": subject, "text": text.format(title=event.title), "html": "",
                          "link": local_link(space, "member")})


def eligible(envelope):
    expected = {"certificate_ready": "active", "certificate_revoked": "revoked"}.get(envelope.event)
    row = EventAttendanceCertificate.objects.filter(pk=envelope.context.get("certificate_id"),
            event_id=envelope.context.get("event_id"), recipient_member_id=envelope.recipient_id,
            status=expected, revision=envelope.revision).select_related("event__makerspace").first() if expected else None
    return bool(row and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events"))


def document_for_recipient(*, certificate_id, recipient_id, revision):
    """F calls this from private provider-media authorization; no badge source exists."""
    from .subjects import require_read
    row = EventAttendanceCertificate.objects.filter(pk=certificate_id, recipient_member_id=recipient_id,
                                                     revision=revision, status="active").first()
    if not row:
        return None
    require_read(row, row.recipient_member)
    return {"object_key": row.object_key, "sha256": row.sha256, "size_bytes": row.size_bytes,
            "content_type": "application/pdf", "filename": f"certificate-{row.serial}.pdf",
            "event_id": row.event_id, "recipient_id": recipient_id, "revision": row.revision}
