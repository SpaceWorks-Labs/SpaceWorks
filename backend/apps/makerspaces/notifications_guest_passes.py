"""Decision 223 notices, through the notification pipeline (feature `members`, stream `membership`).

* `guest_pass_issued` -- to the holder when a pass is issued (the pass id and window only).
* `guest_pass_expiring` -- to the holder in the hour before the pass ends (`send_expiring_notices`
  is the sweep body; scheduling it is the caller's job).
* `guest_pass_sponsor_notice` -- to the sponsor of a sponsored guest. Lane L1b calls
  `notify_sponsor(pass, reason)` for "items outstanding" and incident notices; `reason` is a
  short fixed code, never free text and never the guest's other history.

All three are gated by `membership.guest_passes` (notification_catalog_sources), reserve their
intent inside the domain transaction and re-check eligibility at send time.
"""
from datetime import timedelta

from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped

from .models import GuestPass

SOURCE = "membership.guest_pass"
SPONSOR_REASONS = {"items_outstanding", "incident", "pass_revoked"}
_TEXT = {
    "guest_pass_issued": "Your guest pass at {space} is ready. It is valid until {until:%Y-%m-%d %H:%M} ({tz}).",
    "guest_pass_expiring": "Your guest pass at {space} ends within the hour.",
    "guest_pass_sponsor_notice": "There is an update on the guest you brought to {space} (see My guests).",
}


def _load(envelope):
    return scoped(GuestPass, envelope.makerspace_id).select_related("makerspace").filter(pk=envelope.source_id).first()


def _content(row, event):
    from apps.makerspaces.local_time import to_local
    local = to_local(row.makerspace, row.valid_until)  # m13: the space's wall clock, not UTC
    text = _TEXT[event].format(space=row.makerspace.name, until=local, tz=local.tzname())
    titles = {"guest_pass_issued": "Guest pass issued", "guest_pass_expiring": "Guest pass ending",
              "guest_pass_sponsor_notice": "Update on your guest"}
    return body(titles[event], text, local_link(row.makerspace, "member"))


def _eligible(envelope):
    row = _load(envelope)
    if row is None or envelope.event not in _TEXT:
        return False
    recipient = row.sponsor_id if envelope.event == "guest_pass_sponsor_notice" else row.holder_id
    if recipient != envelope.recipient_id:
        return False
    if envelope.event == "guest_pass_sponsor_notice":
        return envelope.revision == revision(row.pk, envelope.context.get("reason", ""))
    return row.status in GuestPass.LIVE_STATUSES and envelope.revision == revision(row.pk, row.valid_until.isoformat())


def _send(row, event, owner, rev, context=None):
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event=event,
                  source_kind=SOURCE, revision=rev, owner=owner, owner_body=_content(row, event), staff=False,
                  context=context or {})


@safe_notification
def notify_pass_issued(row):
    return _send(row, "guest_pass_issued", row.holder, revision(row.pk, row.valid_until.isoformat()))


@safe_notification
def notify_pass_expiring(row):
    return _send(row, "guest_pass_expiring", row.holder, revision(row.pk, row.valid_until.isoformat()))


@safe_notification
def notify_sponsor(row, reason):
    if row.sponsor_id is None or reason not in SPONSOR_REASONS:
        return None
    return _send(row, "guest_pass_sponsor_notice", row.sponsor, revision(row.pk, reason), {"reason": reason})


def send_expiring_notices(now=None, makerspace=None):
    """Notify holders whose live pass ends within the hour. Idempotent per pass window."""
    now = now or timezone.now()
    rows = GuestPass.objects.select_related("makerspace", "holder").filter(
        status__in=GuestPass.LIVE_STATUSES, valid_until__gt=now, valid_until__lte=now + timedelta(hours=1))
    if makerspace is not None:
        rows = rows.filter(makerspace=makerspace)
    from apps.integrations.models_contract import NotificationEnvelope
    count = 0
    for row in rows[:500]:
        # The envelope dedup key already makes a repeat a no-op; skipping a pass whose notice
        # for this window exists keeps the sweep's "notified" count honest (decision 246).
        if NotificationEnvelope.objects.filter(
            makerspace_id=row.makerspace_id, source_kind=SOURCE, source_id=str(row.pk),
            event="guest_pass_expiring", revision=revision(row.pk, row.valid_until.isoformat()),
        ).exists():
            continue
        notify_pass_expiring(row)
        count += 1
    return count


def register():
    register_source(SOURCE, NotificationSource(_eligible, lambda envelope: _content(_load(envelope), envelope.event)))
