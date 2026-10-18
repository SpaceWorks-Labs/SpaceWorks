from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.events import event_authority
from apps.events.checkin_policy import download_is_open
from apps.events.checkin_roster import host_waiver_state
from apps.events.event_permissions import CHECK_IN
from apps.events.models_attendance import EventCheckInEvent
from apps.events.models_registration import EventRegistration

from .boundary import event_command
from .crypto import token_digest
from .errors import ProgrammeConflict
from .models import EventRegistrationCredential
from .workflow import require_eligible


def resolve(event, payload, *, actor):
    event_authority.require(actor, event, CHECK_IN)
    if not download_is_open(event):
        raise NotFound()
    digest = token_digest(event.pk, payload)
    if digest is None:
        raise NotFound()
    credential = EventRegistrationCredential.objects.filter(
        token_digest=digest, registration__event=event, registration__credential_mode="v2",
        revoked_at__isnull=True, expires_at__gt=timezone.now(),
    ).select_related("registration").first()
    if credential is None:
        raise NotFound()
    registration = credential.registration
    registration.event = event
    require_eligible(event, registration)
    attendance = EventCheckInEvent.objects.filter(registration=registration).order_by("-recorded_at", "-pk").first()
    return {"registration_id": registration.pk, "member_id": registration.member_id,
            "name": registration.name, "status": registration.status,
            "attended_at": attendance.attended_at if attendance and registration.status == "attended" else None,
            "ticket_type_name": registration.ticket_type.name if registration.ticket_type_id else None,
            "host_waiver_state": host_waiver_state(registration),
            "confirmable": registration.status == "registered", "credential_generation": credential.generation}


def confirm(event_id, payload, *, actor, operation_id, credential_generation):
    """G's attendance command dispatches here for SWEC2; existing attendance remains sole writer."""
    from apps.events.services_checkin import mark_attended_with_event

    with event_command(event_id, actor=actor, permission=CHECK_IN) as (event, actor):
        result = resolve(event, payload, actor=actor)
        if result["credential_generation"] != credential_generation:
            raise ProgrammeConflict("This badge was replaced.", code="credential_changed")
        previous = EventCheckInEvent.objects.filter(makerspace_id=event.makerspace_id,
                                                    operation_id=operation_id).first()
        if previous:
            if previous.event_id != event.pk or previous.registration_id != result["registration_id"]:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return result
        registration = EventRegistration.objects.select_for_update().get(pk=result["registration_id"])
        mark_attended_with_event(registration, actor=actor, operation_id=operation_id,
                                 source=EventCheckInEvent.Source.QR)
        return resolve(event, payload, actor=actor)
