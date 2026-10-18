from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record
from apps.events.certificate_templates import issuance_layout
from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.exceptions import EventInvalidTransition
from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.models_certificate_templates import EventCertificateTemplateRevision
from apps.makerspaces.platform import feature_enabled

from .models import EventCertificatePublicationPolicy
from .subjects import require_subject


def create_for_subject_locked(event, *, subject_kind, subject_id, kind="attendance", actor=None,
                              award_id=None, result_revision_id=None, response=None,
                              public_verification_enabled=True):
    from apps.events import services_certificates as facade
    if event.status not in ("published", "completed"):
        raise EventInvalidTransition("Certificates require a published or completed event.")
    subject = require_subject(event, subject_kind=subject_kind, subject_id=subject_id, kind=kind,
                              award_id=award_id, result_revision_id=result_revision_id)
    filters = {"registration_id" if subject_kind == "registration" else "role_assignment_id": subject_id,
               "kind": kind, "award_id": award_id}
    previous = EventAttendanceCertificate.objects.filter(**filters)
    live = previous.exclude(status="revoked").first()
    if live:
        return live
    if response is not None and (subject_kind != "registration" or response.registration_id != subject_id):
        raise ProgrammeConflict("Feedback does not belong to this registration.")
    template = (EventCertificateTemplateRevision.objects.filter(event=event).select_related("artwork").first()
                if feature_enabled(event.makerspace, "events.certificate_designer") else None)
    revision = (previous.aggregate(value=Max("revision"))["value"] or 0) + 1
    publication = EventCertificatePublicationPolicy.objects.filter(event=event, enabled=True).exists()
    row = EventAttendanceCertificate(
        event=event, recipient_member_id=subject.member_id, kind=kind,
        revision=revision, response=response, award_id=award_id, result_revision_id=result_revision_id,
        template_revision=template, layout_snapshot=issuance_layout(template),
        recipient_name=subject.recipient_name, event_title=event.title,
        event_starts_at=event.starts_at, event_ends_at=event.ends_at, issuer_name=event.makerspace.name,
        event_timezone_name=event.timezone_name,
        public_verification_enabled=public_verification_enabled and publication, **filters_subject(subject),
    )
    # auto_now_add is populated only at save; preflight uses the same issuance date.
    row.issued_at = timezone.now()
    row.object_key = f"event-certificates/{event.makerspace_id}/{row.serial}.pdf"
    facade.validate_certificate_layout(row)
    row.save()
    record(actor, "event.certificate_created", makerspace=event.makerspace, target=row,
           meta={"revision": revision, "kind": kind, "template_revision_id": row.template_revision_id})
    return row


def filters_subject(subject):
    return {"registration_id" if subject.subject_kind == "registration" else "role_assignment_id": subject.subject_id}


def create_pending(response):
    if response.registration_id is None:
        raise EventInvalidTransition("Attendance is required before certificate creation.")
    with event_command(response.registration.event_id) as (event, _):
        return create_for_subject_locked(event, subject_kind="registration", subject_id=response.registration_id,
                                         response=response, public_verification_enabled=True)


def reissue(registration, *, actor):
    with event_command(registration.event_id, actor=actor) as (event, actor):
        if registration.attendance_certificates.filter(kind="attendance").exclude(status="revoked").exists():
            raise EventInvalidTransition("A live certificate already exists.")
        # Bulk reissue does not fabricate or require a feedback response.
        return create_for_subject_locked(event, subject_kind="registration", subject_id=registration.pk, actor=actor)
