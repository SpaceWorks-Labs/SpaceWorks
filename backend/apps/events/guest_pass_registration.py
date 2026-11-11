"""Decision 223 (a)(b): the event pass follows the registration, not the door.

A `post_save` on `EventRegistration` is the one place every admission path meets (the public form, staff
add, waitlist promotion, approval, a settled ticket order filling a seat, a team admission), so the pass
is issued when a registration BECOMES `registered` and never depends on which flow got it there. Payment
is not a separate gate: a paid ticket reaches `registered` only through the existing flow's own admission
(order settlement seats people; a pending charge on a registered row is the existing model).

* registered  -> `ensure_event_pass` after the surrounding transaction commits (`robust` on_commit, the
  way check-in does), so "My passes" and self equipment planning work before the event. Idempotent: the
  pass's `operation_id` is `event-<event>-reg-<registration>`.
* cancelled   -> `release_event_pass` revokes that pass, unless the holder already checked in (a presence
  session at the space since the pass began) or has items out; then the pass is left and the decision is
  audited. Staff can still revoke by hand.

Inert while `events.guest_passes` is off. A failure never affects the registration or the cancellation.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save

from .guest_pass_adapter import CANCEL_REASON, FEATURE, ensure_event_pass, operation_id

logger = logging.getLogger(__name__)


def _holds_items(guest_pass):
    from apps.hardware_requests.models import HardwareRequest
    return HardwareRequest.objects.filter(
        makerspace_id=guest_pass.makerspace_id, requester_id=guest_pass.holder_id,
        status__in=(HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED)).exists()


def _checked_in(guest_pass):
    from apps.presence.models import PresenceSession
    return PresenceSession.objects.filter(
        makerspace_id=guest_pass.makerspace_id, account_id=guest_pass.holder_id,
        started_at__gte=guest_pass.valid_from).exists()


def release_event_pass(registration_id):
    """Revoke the cancelled registration's live event pass, or audit why it was kept. Never raises."""
    from apps.audit import services as audit
    from apps.makerspaces.guest_pass_lifecycle import revoke_pass
    from apps.makerspaces.models import GuestPass
    from apps.makerspaces.platform import feature_enabled
    from .models import EventRegistration
    try:
        registration = EventRegistration.objects.select_related("event__makerspace").get(pk=registration_id)
        space = registration.event.makerspace
        if registration.status != EventRegistration.Status.CANCELLED or not feature_enabled(space, FEATURE):
            return None
        base = operation_id(registration.event_id, registration.pk)
        guest_pass = GuestPass.objects.filter(
            Q(operation_id=base) | Q(operation_id__startswith=f"{base}-g"),
            makerspace=space, status__in=GuestPass.LIVE_STATUSES).first()
        if guest_pass is None:
            return None
        if _checked_in(guest_pass) or _holds_items(guest_pass):
            audit.record(None, "membership.guest_pass_kept_on_cancel", makerspace=space, target=guest_pass,
                         meta={"registration_id": registration.pk})
            return guest_pass
        return revoke_pass(None, guest_pass, reason=CANCEL_REASON)
    except Exception:
        logger.exception("event_guest_pass_release_failed", extra={"registration_id": registration_id})
        return None


def _saved(sender, instance, update_fields=None, **kwargs):
    if instance.member_id is None or (update_fields is not None and "status" not in update_fields):
        return
    if instance.status == "registered":
        transaction.on_commit(lambda: ensure_event_pass(instance.pk), robust=True)
    elif instance.status == "cancelled":
        transaction.on_commit(lambda: release_event_pass(instance.pk), robust=True)


def connect_signals():
    from .models import EventRegistration
    post_save.connect(_saved, sender=EventRegistration, dispatch_uid="events.guest_pass_registration.saved")
