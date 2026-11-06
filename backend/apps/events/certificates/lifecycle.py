import logging
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.events.certificate_storage import CertificateStorageUnavailable, presigned_download
from apps.events.exceptions import EventInvalidTransition
from apps.events.models_certificates import EventAttendanceCertificate as Certificate
from apps.makerspaces import limits
from .subjects import require_subject, require_read
from .locked import certificate_command, save_operational

logger = logging.getLogger(__name__)


def _eligible(row, prepared):
    if row.event.status not in ("published", "completed"):
        raise EventInvalidTransition("The event no longer permits certificate rendering.")
    from .contribution_proof import require_current
    require_current(row)
    return require_subject(row.event, subject_kind="registration" if row.registration_id else "role_assignment",
                           subject_id=row.registration_id or row.role_assignment_id, kind=row.kind,
                           award_id=row.award_id, result_revision_id=row.result_revision_id, prepared=prepared)


def render_certificate(certificate):
    from apps.events import services_certificates as facade
    row = _claim_render(certificate.pk)
    if row.status == "active":
        return row
    rendered = False
    try:
        payload = facade.render_certificate_pdf(row)
        rendered = True
        size, digest = facade.store_immutable_pdf(row.object_key, payload)
        return _activate(row.pk, size, digest, render_token=row.render_token)
    except Exception as exc:
        try:
            _fail_render(row.pk, render_token=row.render_token)
        except Exception:
            logger.warning("event_certificate_failure_deferred", extra={"certificate_id": row.pk})
        from rest_framework.exceptions import APIException, ValidationError
        if isinstance(exc, (EventInvalidTransition, CertificateStorageUnavailable)):
            raise
        # A layout refusal from rendering is the caller's to see. After the PDF exists,
        # a storage-quota refusal is operational: the row is marked failed for retry
        # and the reader gets the uniform storage-unavailable error.
        if isinstance(exc, APIException) and not (rendered and isinstance(exc, ValidationError)):
            raise
        logger.warning("event_certificate_render_failed", extra={"certificate_id": row.pk})
        raise CertificateStorageUnavailable() from exc


def _claim_render(certificate_id):
    with certificate_command(certificate_id) as (event, _, row, prepared):
        _eligible(row, prepared)
        if row.status == "active":
            return row
        from .signatories import require_render_released
        require_render_released(row)
        stale = row.status == "rendering" and (
            row.render_started_at is None or row.render_started_at <= timezone.now()-timedelta(minutes=5))
        if row.status not in ("pending", "failed") and not stale:
            raise EventInvalidTransition("The certificate cannot be claimed for rendering.")
        row.status = "rendering"
        row.render_token, row.render_started_at = uuid4(), timezone.now()
        row.render_attempts += 1
        save_operational(row, ("status", "render_token", "render_started_at", "render_attempts"))
        record(None, "event.certificate_render_claimed", makerspace=event.makerspace, target=row,
               meta={"revision": row.revision})
        return row


def _activate(certificate_id, size, digest, *, render_token):
    with certificate_command(certificate_id) as (event, _, row, prepared):
        _eligible(row, prepared)
        if row.status == "active":
            return row
        if row.status != "rendering" or row.render_token != render_token:
            raise EventInvalidTransition("Certificate render claim was lost.")
        limits.add_storage(event.makerspace, size)
        row.status, row.size_bytes, row.sha256, row.rendered_at = "active", size, digest, timezone.now()
        save_operational(row, ("status", "size_bytes", "sha256", "rendered_at"))
        record(None, "event.certificate_rendered", makerspace=event.makerspace, target=row,
               meta={"revision": row.revision, "size_bytes": size})
        _notify_owner(row, "certificate_ready")
        return row


def _fail_render(certificate_id, *, render_token):
    with certificate_command(certificate_id) as (event, _, row, _prepared):
        if row.status != "rendering" or row.render_token != render_token:
            return
        row.status = "failed"
        save_operational(row, ("status",))
        record(None, "event.certificate_render_failed", makerspace=event.makerspace, target=row,
               meta={"revision": row.revision})


def download_url(certificate, *, actor=None):
    require_read(certificate, actor)
    if certificate.status in ("pending", "failed"):
        certificate = render_certificate(certificate)
    certificate.refresh_from_db()
    require_read(certificate, actor)
    if certificate.status != "active":
        raise EventInvalidTransition("Only active certificates can be downloaded.")
    with certificate_command(certificate.pk) as (_event, _, checked, prepared):
        _eligible(checked, prepared)
    url = presigned_download(certificate.object_key)
    record(actor, "event.certificate_downloaded", makerspace=certificate.event.makerspace,
           target=certificate, meta={"revision": certificate.revision})
    return certificate, url


def revoke(certificate, *, actor, reason):
    with certificate_command(certificate.pk, actor=actor) as (event, actor, row, _prepared):
        return revoke_locked(event, row, actor=actor, reason=reason)


def revoke_locked(event, row, *, actor, reason):
    if row.status != "active":
        raise EventInvalidTransition("Only an active certificate can be revoked.")
    if reason not in Certificate.RevocationReason.values:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"reason": "Choose a certificate revocation reason."})
    row.status, row.revoked_at, row.revoked_by, row.revocation_reason = "revoked", timezone.now(), actor, reason
    save_operational(row, ("status", "revoked_at", "revoked_by", "revocation_reason"))
    record(actor, "event.certificate_revoked", makerspace=event.makerspace, target=row,
           meta={"revision": row.revision, "reason": reason})
    _notify_owner(row, "certificate_revoked")
    return row


def _notify_owner(certificate, event_name):
    from .notifications import certificate_envelope
    try:
        with transaction.atomic():
            certificate_envelope(certificate, event_name)
    except Exception:
        logger.warning("event_certificate_notice_failed", extra={"certificate_id": certificate.pk})
