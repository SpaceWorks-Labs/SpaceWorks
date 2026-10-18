from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record
from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.exceptions import EventInvalidTransition
from apps.events.models_certificates import EventAttendanceCertificate

from .models import EventCertificatePublicationPolicy
from .subjects import require_subject
from .preparation import prepare_issuance, save_prepared


def create_for_subject_locked(event, *, subject_kind, subject_id, kind="attendance", actor=None,
                              award_id=None, result_revision_id=None, response=None,
                              public_verification_enabled=True, prepared=None):
    from apps.events import services_certificates as facade
    if event.status not in ("published", "completed"):
        raise EventInvalidTransition("Certificates require a published or completed event.")
    if prepared is None:
        raise RuntimeError("Prepare certificate subjects before the event transaction.")
    prepared.revalidate(event)
    recipient = prepared.recipient(subject_kind, subject_id)
    subject = require_subject(event, subject_kind=subject_kind, subject_id=subject_id, kind=kind,
                              award_id=award_id, result_revision_id=result_revision_id, prepared=recipient)
    filters = {"registration_id" if subject_kind == "registration" else "role_assignment_id": subject_id,
               "kind": kind, "award_id": award_id}
    previous = EventAttendanceCertificate.objects.filter(**filters)
    live = previous.exclude(status="revoked").first()
    if live:
        return live
    if response is not None and (subject_kind != "registration" or response.registration_id != subject_id):
        raise ProgrammeConflict("Feedback does not belong to this registration.")
    revision = (previous.aggregate(value=Max("revision"))["value"] or 0) + 1
    publication = EventCertificatePublicationPolicy.objects.filter(event=event, enabled=True).exists()
    row = EventAttendanceCertificate(
        event=event, recipient_member_id=subject.member_id, kind=kind,
        revision=revision, response=response, award_id=award_id, result_revision_id=result_revision_id,
        template_revision_id=prepared.template_id, layout_snapshot=prepared.layout,
        recipient_name=subject.recipient_name, event_title=event.title,
        event_starts_at=event.starts_at, event_ends_at=event.ends_at, issuer_name=event.makerspace.name,
        event_timezone_name=event.timezone_name,
        public_verification_enabled=public_verification_enabled and publication, **filters_subject(subject),
    )
    # auto_now_add is populated only at save; preflight uses the same issuance date.
    row.issued_at = timezone.now()
    row.object_key = f"event-certificates/{event.makerspace_id}/{row.serial}.pdf"
    facade.validate_certificate_layout(row)
    save_prepared(row, recipient)
    record(actor, "event.certificate_created", makerspace=event.makerspace, target=row,
           meta={"revision": revision, "kind": kind, "template_revision_id": row.template_revision_id})
    return row


def filters_subject(subject):
    return {"registration_id" if subject.subject_kind == "registration" else "role_assignment_id": subject.subject_id}


def create_pending(response):
    if response.registration_id is None:
        raise EventInvalidTransition("Attendance is required before certificate creation.")
    prepared = prepare_issuance(response.registration.event_id,
        [{"subject_kind": "registration", "subject_id": response.registration_id}])
    with event_command(response.registration.event_id, account_ids=prepared.account_ids,
                       revalidate=prepared.revalidate) as (event, _):
        return create_pending_locked(event, response, prepared=prepared)


def create_pending_locked(event, response, *, prepared, actor=None):
    """Feedback's prepared outer command calls this without reacquiring Event."""
    if response.registration_id is None or response.registration.event_id != event.pk:
        raise EventInvalidTransition("Feedback must belong to this event registration.")
    return create_for_subject_locked(event, subject_kind="registration", subject_id=response.registration_id,
        response=response, actor=actor, public_verification_enabled=True, prepared=prepared)


def reissue(registration, *, actor):
    from apps.events import event_authority
    event_authority.get_event(actor, registration.event_id, None)
    prepared = prepare_issuance(registration.event_id,
        [{"subject_kind": "registration", "subject_id": registration.pk}])
    with event_command(registration.event_id, actor=actor, account_ids=prepared.account_ids,
                       revalidate=prepared.revalidate) as (event, actor):
        if registration.attendance_certificates.filter(kind="attendance").exclude(status="revoked").exists():
            raise EventInvalidTransition("A live certificate already exists.")
        # Bulk reissue does not fabricate or require a feedback response.
        return create_for_subject_locked(event, subject_kind="registration", subject_id=registration.pk,
                                         actor=actor, prepared=prepared)


def reissue_certificate(certificate, *, actor):
    """Legacy HTTP adapter preserves the typed subject/kind/award of the old issuance."""
    from apps.events import event_authority
    event_authority.get_event(actor, certificate.event_id, None)
    subject_kind = "registration" if certificate.registration_id else "role_assignment"
    prepared = prepare_issuance(certificate.event_id, [{"subject_kind": subject_kind,
        "subject_id": certificate.registration_id or certificate.role_assignment_id}])
    with event_command(certificate.event_id, actor=actor, account_ids=prepared.account_ids,
                       revalidate=prepared.revalidate) as (event, actor):
        row = EventAttendanceCertificate.objects.select_for_update().get(pk=certificate.pk, event=event)
        subject_kind = "registration" if row.registration_id else "role_assignment"
        subject_id = row.registration_id or row.role_assignment_id
        filters = {"registration_id" if row.registration_id else "role_assignment_id": subject_id,
                   "kind": row.kind, "award_id": row.award_id}
        if EventAttendanceCertificate.objects.filter(**filters).exclude(status="revoked").exists():
            raise EventInvalidTransition("A live certificate already exists.")
        return create_for_subject_locked(event, subject_kind=subject_kind, subject_id=subject_id,
            actor=actor, kind=row.kind, award_id=row.award_id, result_revision_id=row.result_revision_id,
            public_verification_enabled=row.public_verification_enabled, prepared=prepared)
