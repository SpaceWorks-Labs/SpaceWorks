"""Append-only attendance correction with certificate revocation."""

from django.utils import timezone
from .exceptions import EventInvalidTransition
from .models import EventAttendanceCertificate, EventRegistration
from .registration_locks import _boundary, _lock_registration
from .services_write_boundary import event_write

@event_write(permission="check_in")
def correct_attendance(registration, *, actor):
    services = _boundary()
    event = services._locked_event(registration.event_id)
    locked = _lock_registration(event, registration.pk)
    if locked.status != EventRegistration.Status.ATTENDED:
        raise EventInvalidTransition("Only attended registrations can be corrected.")
    certificates = list(
        EventAttendanceCertificate.objects.select_for_update().filter(
            registration=locked,
            status=EventAttendanceCertificate.Status.ACTIVE,
        )
    )
    locked.status = EventRegistration.Status.REGISTERED
    locked.version += 1
    from .attendance_payout_bridge import attended_locked, corrected_locked, publish_payout_eligibility_locked
    # A correction is an attendance transition too: the revision moves first, then the
    # watermark records it, so an older scan can never qualify again.
    locked.save(update_fields=["status", "version", *attended_locked(locked)])
    marker = corrected_locked(event=event, registration=locked, actor=actor)
    from .hackathons.admission_lifecycle import attendance_changed_locked
    from .programme_locks import current_locks
    attendance_changed_locked(event=event, registration=locked, actor=actor, locks=current_locks(event.pk))
    now = timezone.now()
    for certificate in certificates:
        certificate.status = EventAttendanceCertificate.Status.REVOKED
        certificate.revoked_at = now
        certificate.revoked_by = actor
        certificate.revocation_reason = (
            EventAttendanceCertificate.RevocationReason.ATTENDANCE_CORRECTED
        )
        certificate.save(
            update_fields=[
                "status", "revoked_at", "revoked_by", "revocation_reason",
            ]
        )
        services._audit(
            event,
            actor,
            "event.certificate_revoked",
            certificate,
            {"reason": certificate.revocation_reason, "revision": certificate.revision},
        )
    services._audit(
        event,
        actor,
        "event.registration_attendance_corrected",
        locked,
        {"registration_id": locked.pk, "revoked_certificates": len(certificates),
         "correction_id": marker.pk if marker else None},
    )
    publish_payout_eligibility_locked(event=event, registration=locked, actor=actor)
    return services._refresh(locked), certificates
