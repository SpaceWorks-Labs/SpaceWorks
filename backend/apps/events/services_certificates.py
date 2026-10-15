import logging

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.events.certificate_rendering import render_certificate_pdf, validate_certificate_layout
from apps.events.certificate_storage import (
    CertificateStorageUnavailable,
    presigned_download,
    store_immutable_pdf,
)
from apps.events.exceptions import EventInvalidTransition
from apps.events.models import Event, EventAttendanceCertificate, EventRegistration
from apps.makerspaces import limits


logger = logging.getLogger(__name__)


@transaction.atomic
def create_pending(response):
    from apps.events.certificate_templates import issuance_layout
    from apps.events.models import EventCertificateTemplateRevision
    from apps.makerspaces.platform import feature_enabled
    from apps.makerspaces.guards import require_module_locked
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    event_id = response.registration.event_id if response.registration_id else None
    if event_id is None:
        raise EventInvalidTransition("Attendance is required before certificate creation.")
    event = Event.objects.select_for_update().get(pk=event_id)
    assert_write_allowed(event.makerspace_id)
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    if event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED):
        raise EventInvalidTransition("Certificates require a published or completed event.")
    registration = EventRegistration.objects.select_for_update().get(pk=response.registration_id)
    if (
        registration is None
        or registration.status != EventRegistration.Status.ATTENDED
    ):
        raise EventInvalidTransition(
            "Attendance is required before a certificate can be created."
        )
    template = (EventCertificateTemplateRevision.objects.filter(event=event).select_related("artwork").first()
                if feature_enabled(event.makerspace, "events.certificate_designer") else None)
    revision = (
        EventAttendanceCertificate.objects.filter(registration=registration)
        .aggregate(value=Max("revision"))["value"]
        or 0
    ) + 1
    certificate = EventAttendanceCertificate(
        response=response,
        registration=registration,
        revision=revision,
        template_revision=template,
        layout_snapshot=issuance_layout(template),
        recipient_name=registration.name,
        event_title=event.title,
        event_starts_at=event.starts_at,
        event_ends_at=event.ends_at,
        issuer_name=event.makerspace.name,
    )
    certificate.object_key = (
        f"event-certificates/{event.makerspace_id}/{certificate.serial}.pdf"
    )
    validate_certificate_layout(certificate)
    certificate.save()
    audit.record(None, "event.certificate_created", makerspace=event.makerspace,
                 target=certificate, meta={"revision": revision, "template_revision_id": certificate.template_revision_id})
    return certificate


def render_certificate(certificate):
    claim = _claim_render(certificate.pk)
    if claim.status == EventAttendanceCertificate.Status.ACTIVE:
        return claim
    try:
        payload = render_certificate_pdf(claim)
    except ValidationError:
        _fail_render(claim.pk)
        raise
    except Exception as exc:
        _raise_render_failure(claim, exc)
    try:
        size, digest = store_immutable_pdf(claim.object_key, payload)
        return _activate(claim.pk, size, digest)
    except Exception as exc:
        _raise_render_failure(claim, exc)


def _raise_render_failure(claim, exc):
    _fail_render(claim.pk)
    if isinstance(exc, (EventInvalidTransition, CertificateStorageUnavailable)):
        raise exc
    logger.exception("event_certificate_render_failed", extra={"certificate_id": claim.pk})
    raise CertificateStorageUnavailable from exc


def download_url(certificate, *, actor=None):
    if certificate.status == EventAttendanceCertificate.Status.REVOKED:
        raise EventInvalidTransition("Revoked certificates cannot be downloaded.")
    if certificate.status in {
        EventAttendanceCertificate.Status.PENDING,
        EventAttendanceCertificate.Status.FAILED,
    }:
        certificate = render_certificate(certificate)
    if certificate.status != EventAttendanceCertificate.Status.ACTIVE:
        raise EventInvalidTransition("Certificate rendering is still in progress.")
    url = presigned_download(certificate.object_key)
    audit.record(actor, "event.certificate_downloaded", makerspace=certificate.registration.event.makerspace,
                 target=certificate, meta={"revision": certificate.revision})
    return certificate, url


@transaction.atomic
def revoke(certificate, *, actor, reason):
    from apps.events import event_authority
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    event = Event.objects.select_for_update().get(pk=certificate.registration.event_id)
    assert_write_allowed(event.makerspace_id)
    from apps.makerspaces.guards import require_module_locked
    from apps.events.staff_grant_locks import lock_authority
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    actor = lock_authority(actor, event)
    event_authority.require(actor, event, None)
    locked = EventAttendanceCertificate.objects.select_for_update().select_related(
        "registration__event__makerspace"
    ).get(pk=certificate.pk)
    if locked.status != EventAttendanceCertificate.Status.ACTIVE:
        raise EventInvalidTransition("Only an active certificate can be revoked.")
    locked.status = EventAttendanceCertificate.Status.REVOKED
    locked.revoked_at = timezone.now()
    locked.revoked_by = actor
    locked.revocation_reason = reason
    locked.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason"])
    audit.record(
        actor,
        "event.certificate_revoked",
        makerspace=locked.registration.event.makerspace,
        target=locked,
        meta={"reason": reason, "revision": locked.revision},
    )
    return locked


@transaction.atomic
def reissue(registration, *, actor):
    from apps.events import event_authority
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    event = Event.objects.select_for_update().get(pk=registration.event_id)
    assert_write_allowed(event.makerspace_id)
    from apps.makerspaces.guards import require_module_locked
    from apps.events.staff_grant_locks import lock_authority
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    actor = lock_authority(actor, event)
    event_authority.require(actor, event, None)
    locked = EventRegistration.objects.select_for_update().select_related(
        "event__makerspace"
    ).get(pk=registration.pk)
    if locked.status != EventRegistration.Status.ATTENDED:
        raise EventInvalidTransition("Attendance is required for certificate reissue.")
    if locked.attendance_certificates.exclude(
        status=EventAttendanceCertificate.Status.REVOKED
    ).exists():
        raise EventInvalidTransition("A live certificate already exists.")
    response = locked.feedback_responses.order_by("-created_at", "-id").first()
    if response is None:
        raise EventInvalidTransition("Feedback is required for certificate reissue.")
    certificate = create_pending(response)
    audit.record(
        actor,
        "event.certificate_reissued",
        makerspace=locked.event.makerspace,
        target=certificate,
        meta={"revision": certificate.revision},
    )
    return certificate


@transaction.atomic
def _claim_render(certificate_id):
    identity = EventAttendanceCertificate.objects.values(
        "registration_id", "registration__event_id"
    ).get(pk=certificate_id)
    Event.objects.select_for_update().get(pk=identity["registration__event_id"])
    registration = EventRegistration.objects.select_for_update().get(
        pk=identity["registration_id"]
    )
    row = EventAttendanceCertificate.objects.select_for_update().select_related(
        "registration__event__makerspace"
    ).get(pk=certificate_id)
    if registration.status != EventRegistration.Status.ATTENDED:
        raise EventInvalidTransition("Attendance is required to render a certificate.")
    if row.status == EventAttendanceCertificate.Status.ACTIVE:
        return row
    if row.status == EventAttendanceCertificate.Status.RENDERING:
        raise EventInvalidTransition("Certificate rendering is already in progress.")
    if row.status == EventAttendanceCertificate.Status.REVOKED:
        raise EventInvalidTransition("Revoked certificates cannot be rendered.")
    row.status = EventAttendanceCertificate.Status.RENDERING
    row.save(update_fields=["status"])
    audit.record(None, "event.certificate_render_claimed", makerspace=row.registration.event.makerspace,
                 target=row, meta={"revision": row.revision})
    return row


@transaction.atomic
def _activate(certificate_id, size, digest):
    identity = EventAttendanceCertificate.objects.values(
        "registration_id", "registration__event_id"
    ).get(pk=certificate_id)
    Event.objects.select_for_update().get(pk=identity["registration__event_id"])
    registration = EventRegistration.objects.select_for_update().get(
        pk=identity["registration_id"]
    )
    row = EventAttendanceCertificate.objects.select_for_update().select_related(
        "registration__event__makerspace"
    ).get(pk=certificate_id)
    if row.status == EventAttendanceCertificate.Status.ACTIVE:
        return row
    if row.status != EventAttendanceCertificate.Status.RENDERING:
        raise EventInvalidTransition("Certificate render claim was lost.")
    if registration.status != EventRegistration.Status.ATTENDED:
        row.status = EventAttendanceCertificate.Status.FAILED
        row.save(update_fields=["status"])
        raise EventInvalidTransition("Attendance changed while rendering the certificate.")
    limits.add_storage(row.registration.event.makerspace, size)
    row.size_bytes = size
    row.sha256 = digest
    row.rendered_at = timezone.now()
    row.status = EventAttendanceCertificate.Status.ACTIVE
    row.save(update_fields=["size_bytes", "sha256", "rendered_at", "status"])
    audit.record(
        None,
        "event.certificate_rendered",
        makerspace=row.registration.event.makerspace,
        target=row,
        meta={"revision": row.revision, "size_bytes": size},
    )
    return row


@transaction.atomic
def _fail_render(certificate_id):
    row = EventAttendanceCertificate.objects.select_for_update().select_related(
        "registration__event__makerspace"
    ).get(pk=certificate_id)
    if row.status != EventAttendanceCertificate.Status.RENDERING:
        return
    row.status = EventAttendanceCertificate.Status.FAILED
    row.save(update_fields=["status"])
    audit.record(
        None,
        "event.certificate_render_failed",
        makerspace=row.registration.event.makerspace,
        target=row,
        meta={"revision": row.revision},
    )
