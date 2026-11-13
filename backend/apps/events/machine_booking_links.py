"""Link workshop machine time to an event, and replace a linked machine booking (P2-1).

A machine link never touches money. The linked booking keeps the machine-time charge its
own admission and pricing raised (`create_booking` / staff price confirmation); the
event's single Booking-owned ROOM charge (decision 216, `EventBookingDecision`) and its
venue-fee rules are untouched, and no event venue fee is consulted or raised here.

Linking re-runs the admission seams that apply to an already-admitted booking -- the
booker's certification for the machine type (`_require_certification`, override honoured
only for type authority and audited) and the repair gate (`_refuse_machine_under_repair`)
-- and never restates them. A maintenance lockout stays advisory, as it is at admission;
the panel shows it through `bookings.admission_readiness`.

Replacement follows the room rules exactly: only a rejected or cancelled current booking,
at most once, through `bookings.services_replacement.replace_booking` (ordinary admission,
staff-confirmed price); the link keeps naming the original and the current reservation
is the chain's tail.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.audit.services import record
from apps.hardware_requests.loan_context_access import safe_id
from .booking_decision_replacement import replaceable, reservation_chain
from .machine_link_access import (
    authorized_machine_booking, authorized_workshop_event, can_manage_machine_space,
    require_organizer_certification,
)
from .models_machine_booking_link import EventMachineBookingLink
from .services_write_boundary import write_boundary

#: An event lists and admits at most this many workshop machine links.
MAX_LINKS = 50
FEATURE = "machines.time_booking"


class WorkshopMachineConflict(APIException):
    status_code = 409
    default_code = "workshop_machine_conflict"

    def __init__(self, code):
        super().__init__({"detail": "Workshop machine link cannot be applied.", "code": code})


def link_machine_booking(actor, maker, event_id, *, booking_id, override_reason=""):
    """Return `(link, replayed)`. Linking the same booking to the same event again replays."""
    event = authorized_workshop_event(actor, maker, event_id)
    authorized_machine_booking(actor, maker, booking_id)
    with write_boundary(event, actor=actor):
        from apps.bookings.admission import _refuse_machine_under_repair, require_feature
        from apps.bookings.models import Booking
        from apps.bookings.services_bookings import _require_certification
        event = authorized_workshop_event(actor, maker, event_id)
        booking = Booking.objects.select_for_update(of=("self",)).select_related("space__makerspace").filter(
            pk=booking_id, space__makerspace_id=maker.pk).first()
        if booking is None:
            raise NotFound()
        authorized_machine_booking(actor, maker, booking.pk)
        existing = EventMachineBookingLink.objects.filter(booking_id=booking.pk, unlinked_at__isnull=True).first()
        if existing is not None:
            if existing.event_id == event.pk and existing.makerspace_id == maker.pk:
                return existing, True
            raise WorkshopMachineConflict("booking_already_linked")
        space = booking.space
        if (event.status not in (event.Status.DRAFT, event.Status.PUBLISHED) or not space.is_active
                or space.machine_id is None or booking.replaces_id is not None
                or booking.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED)
                or booking.ends_at <= timezone.now()):
            # A replacement already belongs to the chain of the booking it replaced.
            raise WorkshopMachineConflict("not_linkable")
        if EventMachineBookingLink.objects.filter(event_id=event.pk, unlinked_at__isnull=True).count() >= MAX_LINKS:
            raise WorkshopMachineConflict("too_many_machines")
        require_feature(space, FEATURE)
        if booking.member_id is None:
            raise WorkshopMachineConflict("booker_required")
        member = type(actor).objects.get(pk=booking.member_id)
        _require_certification(space, member, actor, override_reason)
        require_organizer_certification(event, space, actor, override_reason)
        _refuse_machine_under_repair(space, booking)
        row = EventMachineBookingLink.objects.create(makerspace=maker, event=event, booking=booking)
        # IDs live on the booking-owned rows; the event row names only the operation.
        record(actor, "event.workshop_machine_linked", makerspace=maker, target=event,
               meta={"domain": "booking", "operation": "workshop_machine_linked"})
        return row, False


def _require_tenant_wide_machine_authority(actor, maker):
    from apps.accounts import rbac
    from apps.machines import role_scope
    if not (rbac.can(actor, rbac.Action.MANAGE_MACHINES, maker.pk)
            and role_scope.manage_scope_for(actor, maker.pk) is role_scope.EXEMPT):
        raise NotFound()


def unlink_machine_booking(actor, maker, event_id, link_id):
    """End a live workshop machine link (decision 221b). The booking, its charge and every
    fact of the link are untouched; only the one-way `unlinked_at` marker is set. A second
    unlink of the same link is a replay (`False`)."""
    event = authorized_workshop_event(actor, maker, event_id)
    with write_boundary(event, actor=actor):
        link = EventMachineBookingLink.objects.select_for_update(of=("self",)).filter(
            makerspace_id=maker.pk, event_id=event.pk, pk=safe_id(link_id)).first()
        if link is None:
            raise NotFound()
        if link.booking_id is not None:
            authorized_machine_booking(actor, maker, link.booking_id)
        else:
            # The booking is gone, so the link names no machine to authorize against (open item B3):
            # only tenant-wide machine authority (never a type-scoped manager) may end it.
            _require_tenant_wide_machine_authority(actor, maker)
        if link.unlinked_at is not None:
            return link, False
        link.end()
        record(actor, "event.workshop_machine_unlinked", makerspace=maker, target=event,
               meta={"domain": "booking", "operation": "workshop_machine_unlinked", "link_id": link.pk})
        return link, True


@transaction.atomic
def replace_machine_link(actor, maker, event_id, link_id, *, expected_booking_id, space_id, member_id,
                         starts_at, ends_at, price_confirmation, note="", override_reason=""):
    from apps.bookings.admission import require_feature
    from apps.bookings.booking_authority import get_space
    from apps.bookings.services_replacement import replace_booking
    from apps.bookings.views_admin_booking_create import _members
    from apps.presence.guard import require_active_member

    event = authorized_workshop_event(actor, maker, event_id)
    link = EventMachineBookingLink.objects.filter(makerspace_id=maker.pk, event_id=event.pk,
                                                  pk=safe_id(link_id), unlinked_at__isnull=True).first()
    if link is None or link.booking_id is None:
        raise NotFound()
    current = reservation_chain(actor, maker, link, authorize=authorized_machine_booking)[-1]
    if current.pk != expected_booking_id:
        raise WorkshopMachineConflict("stale_context")
    if not replaceable(event, current):
        raise WorkshopMachineConflict("replacement_not_allowed")
    space = get_space(actor, space_id, "manage_reservations")
    if (space.makerspace_id != maker.pk or not space.is_active or space.machine_id is None
            or not can_manage_machine_space(actor, space)):
        raise NotFound()
    require_feature(space, FEATURE)
    require_organizer_certification(event, space, actor, override_reason)
    membership = get_object_or_404(_members(actor, space), user_id=member_id)
    require_active_member(membership.user, maker)
    replacement = replace_booking(current, space=space, member=membership.user, starts_at=starts_at,
                                  ends_at=ends_at, actor=actor, price_confirmation=price_confirmation,
                                  note=note, certification_override_reason=override_reason)
    record(actor, "event.workshop_machine_replaced", makerspace=maker, target=event,
           meta={"domain": "booking", "operation": "workshop_machine_replaced"})
    return replacement
