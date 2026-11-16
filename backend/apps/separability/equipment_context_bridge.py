"""Two explicit optional-domain adapters for contextual equipment proposals."""
from django.apps import apps
from django.http import Http404
from apps.separability.registry import runtime_active


def _available(name):
    if not apps.is_installed("apps." + name) or not runtime_active(name):
        raise Http404


def observe_event(makerspace_id, registration_id):
    _available("events")
    from apps.events.models import EventRegistration
    value = EventRegistration.objects.filter(
        pk=registration_id, event__makerspace_id=makerspace_id,
    ).values_list("event_id", flat=True).first()
    if value is None:
        raise Http404
    return value


def lock_event(makerspace_id, event_id):
    _available("events")
    from apps.events.models import Event
    event = Event.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=event_id, makerspace_id=makerspace_id,
    ).first()
    if event is None:
        raise Http404
    return event


def lock_registration(event, registration_id):
    _available("events")
    from apps.events.models import EventRegistration
    row = EventRegistration.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=registration_id, event_id=event.pk,
    ).first()
    if row is None:
        raise Http404
    return row


def validate_event(event, registration, maker, borrower, actor):
    _available("events")
    from apps.events.equipment_proposal_target import validate_registration
    return validate_registration(event=event, registration=registration, makerspace_id=maker.pk,
                                 borrower=borrower, staff_actor=actor)


def observe_booking(makerspace_id, booking_id):
    _available("bookings")
    from apps.bookings.models import Booking
    value = Booking.objects.filter(
        pk=booking_id, space__makerspace_id=makerspace_id,
    ).values_list("space_id", flat=True).first()
    if value is None:
        raise Http404
    return value


def lock_space(makerspace_id, space_id):
    _available("bookings")
    from apps.bookings.models import BookableSpace
    row = BookableSpace.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=space_id, makerspace_id=makerspace_id,
    ).first()
    if row is None:
        raise Http404
    return row


def lock_booking(space, booking_id):
    _available("bookings")
    from apps.bookings.models import Booking
    row = Booking.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=booking_id, space_id=space.pk,
    ).first()
    if row is None:
        raise Http404
    return row


def validate_booking(space, booking, maker, borrower, actor):
    _available("bookings")
    from apps.bookings.equipment_proposal_target import validate_booking
    return validate_booking(space=space, booking=booking, makerspace_id=maker.pk,
                            borrower=borrower, staff_actor=actor)


def member_booking_id(maker, borrower, token):
    _available("bookings")
    from apps.accounts.loan_context_identity import borrower_aliases
    from apps.bookings.models import Booking
    try:
        aliases = borrower_aliases(borrower)
    except (ValueError, RuntimeError):
        raise Http404 from None
    value = Booking.objects.filter(
        space__makerspace=maker, member_id__in=aliases, public_token=token,
    ).values_list("pk", flat=True).first()
    if value is None:
        raise Http404
    return value


def preauthorize_staff(maker, actor, registration_id, booking_id):
    """Read-only early authorization before mandatory key provisioning."""
    from apps.accounts.loan_context_identity import borrower_aliases, borrower_survivor
    from apps.accounts.models import User
    from apps.makerspaces.guards import require_module
    registration = booking = None
    if registration_id is not None:
        _available("events")
        from apps.events import event_authority, event_permissions
        from apps.events.models import EventRegistration
        registration = EventRegistration.objects.select_related("event").filter(
            pk=registration_id, event__makerspace=maker,
        ).first()
        if registration is None or not event_authority.can(actor, registration.event, event_permissions.MANAGE_REGISTRATIONS):
            raise Http404
        require_module(maker, "events")
    if booking_id is not None:
        _available("bookings")
        from apps.bookings import booking_authority, booking_permissions
        from apps.bookings.models import Booking
        booking = Booking.objects.select_related("space").filter(pk=booking_id, space__makerspace=maker).first()
        if booking is None or not booking_authority.can(actor, booking.space, booking_permissions.MANAGE_RESERVATIONS):
            raise Http404
        require_module(maker, "bookings")
    members = [row.member_id for row in (registration, booking) if row is not None]
    if not members or any(value is None for value in members):
        raise Http404
    try:
        borrower = borrower_survivor(User.objects.get(pk=members[0]))
        aliases = borrower_aliases(borrower)
    except (User.DoesNotExist, ValueError, RuntimeError):
        raise Http404 from None
    if any(value not in aliases for value in members):
        raise Http404
    if registration is not None:
        validate_event(registration.event, registration, maker, borrower, actor)
    if booking is not None:
        validate_booking(booking.space, booking, maker, borrower, actor)
    return borrower


def preauthorize_self(maker, borrower, registration_id, booking_token):
    """Read-only ownership and module checks after the sticky receipt probe."""
    from apps.makerspaces.guards import require_module
    if registration_id is not None:
        _available("events")
        from apps.events.models import EventRegistration
        registration = EventRegistration.objects.select_related("event").filter(
            pk=registration_id, event__makerspace=maker,
        ).first()
        if registration is None:
            raise Http404
        require_module(maker, "events")
        validate_event(registration.event, registration, maker, borrower, None)
    if booking_token is not None:
        booking_id = member_booking_id(maker, borrower, booking_token)
        from apps.bookings.models import Booking
        booking = Booking.objects.select_related("space").filter(pk=booking_id, space__makerspace=maker).first()
        if booking is None:
            raise Http404
        require_module(maker, "bookings")
        validate_booking(booking.space, booking, maker, borrower, None)


def context_exists(domain, *, maker, result, target, participant=None, plan=False):
    _available(domain)
    if domain == "events":
        if plan:
            from apps.events.models_consumable_plan_context import EventConsumablePlanContext as Model
            return Model.objects.filter(makerspace=maker, plan=result, event=target,
                                        participant_registration=participant, active=True).exists()
        from apps.events.models_loan_context import EventLoanContext as Model
        return Model.objects.filter(makerspace=maker, request=result, event=target,
                                    participant_registration=participant, active=True).exists()
    if domain == "bookings":
        if plan:
            from apps.bookings.models_consumable_plan_context import BookingConsumablePlanContext as Model
            return Model.objects.filter(makerspace=maker, plan=result, booking=target, active=True).exists()
        from apps.bookings.models_loan_context import BookingLoanContext as Model
        return Model.objects.filter(makerspace=maker, request=result, booking=target, active=True).exists()
    raise ValueError("Unknown contextual domain")


def attach_context(domain, *, maker, result, target, actor, participant=None, plan=False):
    _available(domain)
    from apps.audit import services as audit
    if domain == "events":
        if plan:
            from apps.events.models_consumable_plan_context import EventConsumablePlanContext as Model
            row = Model.objects.create(makerspace=maker, plan=result, event=target,
                                       participant_registration=participant, active=True, revision=1)
        else:
            from apps.events.models_loan_context import EventLoanContext as Model
            row = Model.objects.create(makerspace=maker, request=result, event=target,
                                       participant_registration=participant, active=True, revision=1)
    elif domain == "bookings":
        if plan:
            from apps.bookings.models_consumable_plan_context import BookingConsumablePlanContext as Model
            row = Model.objects.create(makerspace=maker, plan=result, booking=target, active=True, revision=1)
        else:
            from apps.bookings.models_loan_context import BookingLoanContext as Model
            row = Model.objects.create(makerspace=maker, request=result, booking=target, active=True, revision=1)
    else:
        raise ValueError("Unknown contextual domain")
    audit.record(actor, "equipment.context_linked", makerspace=maker, target=result,
                 meta={"domain": domain, "kind": "consumable_plan" if plan else "request"})
    return row


def event_return_due(request, issued_at):
    """The linked event's end (plus its return window) as a reviewed loan's due-back, or None.

    Decision 221b: items are due `Event.equipment_return_hours` after the event ends, or
    at the event end when that is unset. None (no live event link, Events off or
    uninstalled, a cancelled event, or a due time already past at issue) leaves the core
    loan-days policy unchanged.
    """
    if not apps.is_installed("apps.events") or not runtime_active("events"):
        return None
    from apps.makerspaces.platform import module_enabled
    if not module_enabled(request.makerspace, "events"):
        return None
    from datetime import timedelta
    from apps.events.models_loan_context import EventLoanContext
    row = EventLoanContext.objects.filter(
        request_id=request.pk, makerspace_id=request.makerspace_id, active=True,
        event__makerspace_id=request.makerspace_id,
    ).exclude(event__status="cancelled").values_list(
        "event__ends_at", "event__equipment_return_hours").first()
    if not row or not row[0]:
        return None
    due = row[0] + timedelta(hours=row[1] or 0)
    return due if due > issued_at else None
