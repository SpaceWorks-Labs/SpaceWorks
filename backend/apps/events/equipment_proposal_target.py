"""Event-owned target checks for an already-locked contextual proposal."""
from django.http import Http404

from apps.accounts.loan_context_identity import borrower_aliases
from apps.events import event_authority, event_permissions
from apps.events.models import Event, EventRegistration


def validate_registration(*, event, registration, makerspace_id, borrower, staff_actor=None):
    """Call after the source gate, domain/maker/registration/borrower locks."""
    if (event.makerspace_id != makerspace_id or registration.event_id != event.pk
            or registration.member_id is None
            or event.status in {Event.Status.CANCELLED, Event.Status.COMPLETED}
            or registration.status not in {
                EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED,
            }):
        raise Http404
    if staff_actor is not None and not event_authority.can(
        staff_actor, event, event_permissions.MANAGE_REGISTRATIONS,
    ):
        raise Http404
    try:
        aliases = borrower_aliases(borrower)
    except (ValueError, RuntimeError):
        raise Http404 from None
    if registration.member_id not in aliases:
        raise Http404
    return registration.member_id
