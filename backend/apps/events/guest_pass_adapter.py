"""Decision 223 (a)(b): non-member registrants get an event guest pass (core never imports events).

`ensure_event_pass` is the events side of `makerspaces.guest_pass_issue.issue_event_pass`. It runs
only while `events.guest_passes` (which needs `membership.guest_passes`) is on for the space, for a
registration with an account that is not a member here, and gives the pass the event window
(start - 1 h to end + the event's equipment-return hours). The registration is the link: the pass's
`operation_id` is `event-<event>-reg-<registration>`, so a repeat (a re-scan, a retry, the planning
tool) returns the same pass, and a revoked pass is never silently re-issued.

Issued at registration (`guest_pass_registration`, when the registration becomes `registered`), or else at the first of: staff check-in (`schedule_event_pass`, after the attendance commits) or
equipment planning for that registrant (`equipment_window.plan_for_participants`), so planning
before the event does not need a presence session. A failure never affects attendance or planning.
Check-in itself is the existing location presence session plus the staff desk; a pass opens no door.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)
FEATURE = "events.guest_passes"
ACTIVE_REGISTRATION = ("registered", "attended")
CANCEL_REASON = "event_registration_cancelled"


def operation_id(event_id, registration_id):
    return f"event-{event_id}-reg-{registration_id}"


def current_operation_id(space, event_id, registration_id):
    """The idempotency key the registration's pass lives under right now.

    A pass the holder's own cancellation revoked is spent: registering again must hand out a fresh one,
    under a generation suffix (`-g2`, `-g3`...), or the holder is stuck with a dead pass. A pass STAFF
    revoked (or any other closed state) keeps its key, so it is never silently re-issued.
    """
    from apps.makerspaces.models import GuestPass
    base = operation_id(event_id, registration_id)
    key = base
    for generation in range(2, 50):
        row = GuestPass.objects.filter(makerspace=space, operation_id=key).first()
        cancelled = (row is not None and row.status == GuestPass.Status.REVOKED
                     and row.revoked_by_id is None and row.revoked_reason == CANCEL_REASON)
        if not cancelled:
            return key
        key = f"{base}-g{generation}"
    return key


def ensure_event_pass(registration_id, *, issuer_id=None):
    """The event pass for this registration, issuing it if due; None when none applies. Never raises."""
    from apps.accounts.models import User
    from apps.makerspaces.guest_pass_issue import event_window, issue_event_pass
    from apps.makerspaces.guest_pass_policy import GuestPassError
    from apps.makerspaces.platform import feature_enabled
    from .models import Event, EventRegistration
    try:
        registration = EventRegistration.objects.select_related("event__makerspace", "member").get(pk=registration_id)
        event, holder = registration.event, registration.member
        space = event.makerspace
        if (holder is None or registration.status not in ACTIVE_REGISTRATION
                or event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED)
                or not feature_enabled(space, FEATURE)):
            return None
        issuer = User.objects.filter(pk=issuer_id).first() if issuer_id else None
        valid_from, valid_until = event_window(event.starts_at, event.ends_at or event.starts_at,
                                               event.equipment_return_hours)
        guest_pass, _created = issue_event_pass(
            space, holder, valid_from, valid_until, issuer=issuer,
            operation_id=current_operation_id(space, event.pk, registration.pk))
        return guest_pass
    except GuestPassError:
        return None  # already a member, restricted account, visit cap...: no pass, no error
    except Exception:
        logger.exception("event_guest_pass_failed", extra={"registration_id": registration_id})
        return None


def schedule_event_pass(registration_id, actor=None):
    """Issue after the check-in transaction commits (keeps the event and tenant locks out of it)."""
    issuer_id = getattr(actor, "pk", None)
    transaction.on_commit(lambda: ensure_event_pass(registration_id, issuer_id=issuer_id), robust=True)
