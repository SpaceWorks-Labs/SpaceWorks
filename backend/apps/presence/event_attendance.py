"""Optional post-commit bridge; attendance must never depend on this app."""
import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.tenant_migration.gate_runtime import tenant_write
from .models import PresenceSession
from .policy import presets, require_account, require_enabled

logger = logging.getLogger(__name__)


def ended_event_registrations(now):
    """Registrations whose event has ended: a subquery, so the sweeper never joins or locks events."""
    from apps.events.models import EventRegistration
    return EventRegistration.objects.filter(event__ends_at__lte=now).values("pk")


def event_end_times(rows, now):
    """`{session_pk: event end}` for event-linked sessions whose event has ended by `now`."""
    from apps.events.models import EventRegistration
    linked = {row.event_registration_id: row.pk for row in rows if row.event_registration_id}
    ends = EventRegistration.objects.filter(pk__in=linked, event__ends_at__lte=now).values_list("pk", "event__ends_at")
    return {linked[pk]: ends_at for pk, ends_at in ends}


def event_attendance(registration):
    """Only fresh server-recorded QR/station tickets, never marks or offline replay.

    Re-load every fact after commit. A registration's one-to-one presence link
    makes repeated calls idempotent, including after that presence has ended.
    """
    from apps.events.models import EventRegistration
    from apps.events.services import _locked_event
    from .services import _create, _lock_account
    try:
        registration = EventRegistration.objects.select_related("event__makerspace", "member").get(pk=registration.pk)
        space, account = registration.event.makerspace, registration.member
        try:
            require_enabled(space)
        except NotFound:
            return None
        from apps.makerspaces.platform import module_enabled
        if not module_enabled(space, "events"):
            return None
        if account is None:
            return None
        with tenant_write(space.pk):
            # Match check-in: Event -> Makerspace -> registration. Never acquire
            # the joined Event implicitly after the presence tenant/account locks.
            event = _locked_event(registration.event_id)
            registration = EventRegistration.objects.select_for_update().get(pk=registration.pk, event=event)
            registration.event = event
            account, space = _lock_account(account, space)
            if not module_enabled(space, "events"):
                return None
            now = timezone.now()
            if (registration.status != "attended" or event.status != "published"
                    or not event.starts_at <= now < event.ends_at):
                return None
            evidence = registration.check_in_events.order_by("-recorded_at", "-pk").first()
            if (evidence is None or evidence.source not in {"qr", "venue_station"}
                    or abs((evidence.attended_at - evidence.recorded_at).total_seconds()) > 60
                    or not now - timedelta(seconds=60) <= evidence.recorded_at <= now):
                return None
            previous = PresenceSession.objects.filter(event_registration=registration).first()
            if previous:
                return previous
            membership = require_account(account, space)
            return _create(account, space, membership, max(presets(space)), actor=evidence.actor or account,
                           status="attending_event", registration=registration)
    except Exception:
        # The event transaction is already committed. Never log PII or body text.
        logger.warning("presence_event_hook_skipped", extra={"registration_id": registration.pk})
        return None
