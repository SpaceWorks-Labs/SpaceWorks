"""Decision 223 / audit M5: an event that is cancelled or moved takes its guest passes with it.

The per-registration signal in `guest_pass_registration` only fires when a REGISTRATION row is saved,
and cancelling an event never saves them, so without this module a cancelled event's passes stay live
and a moved event's passes keep the old window. Both entry points run after the surrounding transaction
commits (`robust` on_commit), never raise, and keep a pass whose holder already checked in or holds
items (audited), exactly like `release_event_pass`.
"""
import logging

from django.db import IntegrityError, transaction

from .guest_pass_adapter import CANCEL_REASON, FEATURE

logger = logging.getLogger(__name__)


def _live_event_passes(event):
    from apps.makerspaces.models import GuestPass
    return GuestPass.objects.filter(
        makerspace=event.makerspace, kind=GuestPass.Kind.EVENT, status__in=GuestPass.LIVE_STATUSES,
        operation_id__startswith=f"event-{event.pk}-reg-")


def _keep(guest_pass, event, why):
    from apps.audit import services as audit
    from .guest_pass_registration import _checked_in, _holds_items
    if _checked_in(guest_pass) or _holds_items(guest_pass):
        audit.record(None, "membership.guest_pass_kept_on_cancel", makerspace=event.makerspace, target=guest_pass,
                     meta={"event_id": event.pk, "why": why})
        return True
    return False


def _run(event_id, action):
    from apps.makerspaces.platform import feature_enabled
    from .models import Event
    try:
        event = Event.objects.select_related("makerspace").get(pk=event_id)
        if not feature_enabled(event.makerspace, FEATURE):
            return 0
        done = 0
        for guest_pass in list(_live_event_passes(event)):
            done += 1 if action(event, guest_pass) else 0
        return done
    except Exception:
        logger.exception("event_guest_pass_event_change_failed", extra={"event_id": event_id})
        return 0


def _revoke(event, guest_pass):
    from apps.makerspaces.guest_pass_lifecycle import revoke_pass
    if _keep(guest_pass, event, "event_cancelled"):
        return False
    revoke_pass(None, guest_pass, reason=CANCEL_REASON)
    return True


def _rewindow(event, guest_pass):
    from apps.makerspaces.guest_pass_issue import event_window
    from apps.makerspaces.local_time import to_local
    if _keep(guest_pass, event, "event_moved"):
        return False
    valid_from, valid_until = event_window(event.starts_at, event.ends_at or event.starts_at,
                                           event.equipment_return_hours)
    try:
        with transaction.atomic():
            guest_pass.valid_from, guest_pass.valid_until = valid_from, valid_until
            guest_pass.pass_date = to_local(event.makerspace, valid_from).date()
            guest_pass.save(update_fields=["valid_from", "valid_until", "pass_date"])
    except IntegrityError:  # the holder already has another live pass that day: the old window is not safe
        from apps.makerspaces.models import GuestPass
        _revoke(event, GuestPass.objects.get(pk=guest_pass.pk))
    return True


def revoke_passes_for_cancelled_event(event_id):
    return _run(event_id, _revoke)


def rewindow_passes_for_moved_event(event_id):
    return _run(event_id, _rewindow)


def schedule_cancelled(event):
    transaction.on_commit(lambda: revoke_passes_for_cancelled_event(event.pk), robust=True)


def schedule_moved(event):
    transaction.on_commit(lambda: rewindow_passes_for_moved_event(event.pk), robust=True)
