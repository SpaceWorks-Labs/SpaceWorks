"""What a certificate holder sees and controls (C7-C9): their list, outputs and name disclosure."""
from django.db import transaction
from django.db.models import Q

from apps.audit.services import record
from apps.events.models_certificates import EventAttendanceCertificate
from .merge import frozen_merge, kind_title
from .rendering import verification_url


def verifiable(row):
    """Public verification is on for this certificate and its event, and it rendered."""
    from .models import EventCertificatePublicationPolicy
    return (row.public_verification_enabled and row.status in ("active", "revoked")
            and EventCertificatePublicationPolicy.objects.filter(event_id=row.event_id, enabled=True).exists())


def project(row):
    open_ = verifiable(row)
    return {"id": row.pk, "event_id": row.event_id, "event_title": row.event_title,
            "event_date": row.event_starts_at, "issuer_name": row.issuer_name, "kind": row.kind,
            "kind_title": kind_title(row.kind), "award": frozen_merge(row).get("award", ""),
            "status": row.status, "issued_at": row.issued_at, "revision": row.revision,
            "serial": str(row.serial), "verifiable": open_, "verify_url": verification_url(row) if open_ else None,
            "holder_name_public": row.holder_name_public}


def owned(actor, makerspace_id):
    """The member's own certificates issued through this space (registration or event host)."""
    return (EventAttendanceCertificate.objects.select_related("event", "registration")
            .filter(recipient_member=actor)
            .filter(Q(event__makerspace_id=makerspace_id) | Q(registration__registered_via_makerspace_id=makerspace_id))
            .order_by("-issued_at", "-pk"))


def set_holder_name(row, *, actor, show):
    """Only the holder decides; audited. Changing it never touches the issued PDF."""
    with transaction.atomic():
        locked = EventAttendanceCertificate.objects.select_for_update().get(pk=row.pk, recipient_member=actor)
        if locked.holder_name_public != show:
            EventAttendanceCertificate.objects.filter(pk=locked.pk).update(holder_name_public=show)
            record(actor, "event.certificate_holder_name_changed", makerspace=locked.event.makerspace,
                   target=locked, meta={"show": show})
        locked.holder_name_public = show
    return locked


def record_png(row, *, actor):
    record(actor, "event.certificate_png_downloaded", makerspace=row.event.makerspace, target=row,
           meta={"revision": row.revision})


def record_share_image(row, *, actor):
    record(actor, "event.certificate_share_image_downloaded", makerspace=row.event.makerspace, target=row,
           meta={"revision": row.revision})
