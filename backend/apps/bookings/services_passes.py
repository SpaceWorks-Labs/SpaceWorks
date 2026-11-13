"""Live pass authority and audited renders serialized with booking arrival."""
from django.db import transaction
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.audit import services as audit
from apps.presence.guard import require_active_account
from . import booking_authority
from .confirmation_access import require_feature
from .exceptions import BookingInvalidTransition
from .models import Booking
from .pass_rendering import pass_values, render_pass, sample_values
from .pass_templates import normalize_pass_template
from .services_arrival import require_arrival_access
from .services_bookings import _locked_booking, _locked_space


def require_passes(space):
    require_feature(space.makerspace, "bookings.passes")


@transaction.atomic
def save_pass_template(space, template, *, actor):
    locked = _locked_space(space.pk)
    booking_authority.require(actor, locked, "edit_details")
    require_passes(locked)
    locked.pass_template = normalize_pass_template(template)
    locked.save(update_fields=["pass_template", "updated_at"])
    audit.record(actor, "booking.pass_template_updated", makerspace=locked.makerspace, target=locked)
    return locked.pass_template


@transaction.atomic
def preview_pass(space, template, *, actor):
    locked = _locked_space(space.pk)
    booking_authority.require(actor, locked, "edit_details")
    require_passes(locked)
    # Fixed sample data only. Editors cannot select a real booking for preview.
    payload = render_pass(template, sample_values())
    audit.record(actor, "booking.pass_previewed", makerspace=locked.makerspace, target=locked)
    return payload


@transaction.atomic
def booking_pass(booking, *, actor, scanner=False):
    space, locked = _locked_booking(booking)
    locked.space = space
    require_passes(space)
    if scanner:
        require_arrival_access(actor, space)
        if locked.arrived_at is None:
            raise BookingInvalidTransition("Record an active arrival before printing a staff pass.")
    else:
        require_active_account(actor, space.makerspace)
        if not rbac.scope_personal_bookings(actor, Booking.objects.filter(pk=locked.pk),
                                           makerspace_id=space.makerspace_id).exists():
            raise NotFound()
    if locked.status not in ("confirmed", "completed"):
        raise BookingInvalidTransition("Only confirmed or completed bookings have printable passes.")
    # No cached PDF or confirmation PNG: revalidate the stored template and
    # rebuild an answer-free snapshot after waiting for resource -> booking locks.
    payload = render_pass(space.pass_template, pass_values(locked))
    audit.record(actor, "booking.pass_downloaded", makerspace=space.makerspace, target=locked)
    return payload
