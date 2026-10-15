"""Staff edits and exact cancellation undo under the ordinary event admission lock."""

from django.db import transaction
from django.db.models import CharField, Exists, OuterRef, Q
from django.db.models.functions import Cast
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.events import event_authority
from apps.events.capacity import fresh_registration_status, registration_is_open
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.models import EventRegistration, EventTicketType
from apps.events.registration_access import require_registration_access
from apps.events.services_calendar import calendar_registration_changed
from apps.events.services_registration_state import _lock_registration
from apps.events.ticketing import select_ticket
from apps.forms_schema.validation import validate_answers
from apps.makerspaces.guards import require_module_locked
from apps.operations.cancellation_restore import (
    RestoreRefused, require_exact_restore, require_restorable,
)
from apps.payments.availability import charge_tracking_enabled
from apps.payments.models import Payment

RESTORABLE = (EventRegistration.Status.REGISTERED, EventRegistration.Status.WAITLISTED,
              EventRegistration.Status.PENDING_APPROVAL)


def annotate_registration_restore_history(queryset):
    """Read projection: check durable history in SQL once for the entire roster."""
    return queryset.select_related("event__makerspace").annotate(
        restore_has_consumption=Exists(AuditLog.objects.filter(
            makerspace_id=OuterRef("event__makerspace_id"),
            target_type="events.eventregistration",
            target_id=Cast(OuterRef("pk"), output_field=CharField()),
            action__in=("event.invite_redeemed", "event.promo_redeemed"),
        )),
        restore_has_charge=Exists(Payment.objects.filter(
            makerspace_id=OuterRef("event__makerspace_id"),
            subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=OuterRef("pk"),
        )),
    )


def has_registration_consumption(registration):
    """A free re-registration can replace quote FKs; consumption history is durable."""
    if (registration.invite_id or registration.promo_code_id
            or registration.discount_amount or registration.registration_audience == "invite"):
        return True
    # Roster rows preload history; locked workflow rows always query fresh history.
    consumed = getattr(registration, "restore_has_consumption", None)
    if consumed is None:
        consumed = AuditLog.objects.filter(
            makerspace_id=registration.event.makerspace_id,
            target_type="events.eventregistration", target_id=str(registration.pk),
            action__in=("event.invite_redeemed", "event.promo_redeemed"),
        ).exists()
    return consumed


def _lock(registration, actor):
    from apps.events import services
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(registration.event.makerspace_id)
    assert_mapped_write_allowed(registration.event.makerspace_id)
    event = services._locked_event(registration.event_id, lock_makerspace=False)
    from .organization_audience import lock_admission_sources
    lock_admission_sources(event, event.registrations.values_list("member_id", flat=True))
    event.makerspace = require_module_locked(event.makerspace, "events")
    event_authority.require(actor, event, MANAGE_REGISTRATIONS)
    ticket_id = EventRegistration.objects.filter(pk=registration.pk).values_list("ticket_type_id", flat=True).get()
    if ticket_id:
        EventTicketType.objects.select_for_update().get(pk=ticket_id, event=event)
    return event, _lock_registration(event, registration.pk)


@transaction.atomic
def edit_registration_answers(registration, *, actor, custom_answers):
    from apps.events import services
    event, locked = _lock(registration, actor)
    locked.custom_answers = validate_answers(event.custom_form, custom_answers)
    locked.save(update_fields=["custom_answers"])
    services._audit(event, actor, "event.registration_answers_edited", locked)
    return locked


def _later_promotion(event, registration):
    later_ids = event.registrations.filter(created_at__gt=registration.created_at).annotate(
        text_id=Cast("pk", output_field=CharField()),
    ).values("text_id")
    return AuditLog.objects.filter(
        makerspace=event.makerspace, action="event.registration_promoted",
        target_type="events.eventregistration", target_id__in=later_ids,
        created_at__gte=registration.cancelled_at,
    ).exists()


@transaction.atomic
def restore_registration(registration, *, actor):
    from apps.events import services
    event, locked = _lock(registration, actor)
    now = timezone.now()
    ticket = locked.ticket_type
    prior = require_restorable(
        locked, now=now, cancelled_status=EventRegistration.Status.CANCELLED,
        allowed_statuses=RESTORABLE,
        has_charge=Payment.objects.filter(
            makerspace=event.makerspace, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=locked.pk,
        ).exists(),
        has_consumption=has_registration_consumption(locked),
        would_charge=bool(locked.member_id and charge_tracking_enabled(event.makerspace, "events")
                          and max(event.payment_amount if ticket is None else ticket.amount,
                                  locked.quoted_amount or 0) > 0),
    )
    if not registration_is_open(event, now):
        raise RestoreRefused("registration_closed", "Registration for this event is closed.")
    if event.registration_audience == "invite":
        raise RestoreRefused("invite_required", "Current admission requires an invitation.")
    via = locked.registered_via_makerspace or event.makerspace
    require_registration_access(event, locked.member, staff=True,
                                collaborative=via.pk != event.makerspace_id, via=via)
    from .organization_audience import require_queued_admission
    require_queued_admission(event, locked)
    select_ticket(event, locked.ticket_type_id, locked.member)
    # Approval survives cancellation, but an approval from an earlier registration
    # cycle must not bypass a newly introduced approval requirement.
    approved = prior == EventRegistration.Status.REGISTERED and AuditLog.objects.filter(
        makerspace=event.makerspace, target_type="events.eventregistration",
        target_id=str(locked.pk),
        created_at__gte=locked.created_at, created_at__lte=locked.cancelled_at,
    ).filter(
        Q(action="event.registration_approved")
        | Q(action="event.registration_promoted", meta__promotion_mode="manual"),
    ).exists()
    admitted = fresh_registration_status(event, ticket, approval_granted=approved)
    # Queued entries occupy no seat. Confirmed entries retain existing approval
    # while rechecking both event and ticket capacity through the admission helper.
    if prior == EventRegistration.Status.REGISTERED:
        require_exact_restore(prior, admitted)
    elif prior == EventRegistration.Status.PENDING_APPROVAL:
        require_exact_restore(prior, admitted)
    if prior == EventRegistration.Status.WAITLISTED and _later_promotion(event, locked):
        locked.waitlist_position_at = now
    locked.status = prior
    locked.cancelled_at = None
    locked.status_before_cancel = ""
    locked.save(update_fields=["status", "cancelled_at", "status_before_cancel", "waitlist_position_at"])
    calendar_registration_changed(locked)
    services._audit(event, actor, "event.registration_restored", locked,
                    {"registration_id": locked.pk, "status": prior})
    services.notify_event_lifecycle(event, "registration_restored", locked.pk)
    return services._refresh(locked)
