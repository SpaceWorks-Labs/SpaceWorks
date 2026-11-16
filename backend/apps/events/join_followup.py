"""Decision 223 (k), lane L3b: the post-event "Join" follow-up to non-member attendees (opt-in per space).

Gated by `membership.join_funnel` and the space's `join_followup_enabled`. The sweep `send_join_followups`
(the scheduler calls it hourly) finds registrations that ATTENDED an event that ended at least
`join_followup_delay_hours` ago (and within the last 14 days) for a person with no membership at the host
space, and sends one notice each. The notice intent is reserved per registration, so a repeated sweep never
sends twice. The notice names the event and links to the member area; it carries no other history.
"""
from datetime import timedelta

from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.community_policy import funnel_on, policy_for
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import module_enabled
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped

from .models import EventRegistration

SOURCE = "events.join_followup"
EVENT = "join_followup"
WINDOW_DAYS = 14


def _load(envelope):
    return scoped(EventRegistration, envelope.makerspace_id, field="event__makerspace_id").select_related(
        "event__makerspace").filter(pk=envelope.source_id).first()


def _content(row):
    space = row.event.makerspace
    text = (f"Thanks for coming to {row.event.title} at {space.name}. If you enjoyed it, you can join "
            f"{space.name} as a member and keep building with us.")
    return body(f"Join {space.name}", text, local_link(space, "member"))


def _funnel_live(space):
    """The funnel switch AND the events module: with Events off no event notice goes out (decision 218)."""
    return funnel_on(space) and module_enabled(space, "events")


def _is_member(space_id, user_id):
    return MakerspaceMembership.objects.filter(makerspace_id=space_id, user_id=user_id, status="active").exists()


def _eligible(envelope):
    row = _load(envelope)
    if row is None or envelope.event != EVENT or row.member_id != envelope.recipient_id:
        return False
    space = row.event.makerspace
    return (_funnel_live(space) and policy_for(space).join_followup_enabled
            and row.status == EventRegistration.Status.ATTENDED and not _is_member(space.pk, row.member_id))


@safe_notification
def notify_join_followup(row):
    space = row.event.makerspace
    return fanout(row=row, space=space, feature="members", stream="membership", event=EVENT, source_kind=SOURCE,
                  revision=revision(row.pk, EVENT), owner=row.member, owner_body=_content(row), staff=False)


def send_join_followups(now=None):
    """Send the follow-up for every eligible attendee of every opted-in space. Returns how many were reserved.

    One tenant at a time inside the skip-and-count source-gate boundary (a frozen space is skipped and retried
    next hour; the 14-day window leaves room for that). Rides the hourly membership sweep.
    """
    from apps.makerspaces.servability import servable_queryset
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    now = now or timezone.now()
    counts = {"skipped": 0}
    total = 0
    for space in servable_queryset().filter(community_policy__join_followup_enabled=True).order_by("pk"):
        if not _funnel_live(space):
            continue
        with fanout_tenant_write(space.pk, operation="join_followup_sweep", counts=counts) as go:
            if not go:
                continue
            total += _send_for_space(space, now)
    return total


def _send_for_space(space, now):
    count = 0
    delay = timedelta(hours=policy_for(space).join_followup_delay_hours)
    rows = (EventRegistration.objects.filter(
        event__makerspace=space, status=EventRegistration.Status.ATTENDED, member__isnull=False,
        event__ends_at__lte=now - delay, event__ends_at__gte=now - delay - timedelta(days=WINDOW_DAYS))
        .select_related("event__makerspace", "member"))
    members = set(MakerspaceMembership.objects.filter(makerspace=space, status="active")
                  .values_list("user_id", flat=True))
    # m18: skip rows whose notice is already reserved (revision is constant per registration), so the
    # first 500 attendees cannot starve every later one; the cap now bounds NEW notices only.
    from django.db.models import CharField, Exists, OuterRef
    from django.db.models.functions import Cast
    from apps.accounts import rbac
    from apps.integrations.models_contract import NotificationEnvelope
    reserved = rbac.scope_notification_policy(NotificationEnvelope.objects.all(), makerspace_id=space.pk).filter(
        source_kind=SOURCE, source_id=Cast(OuterRef("pk"), CharField()))
    for row in rows.exclude(Exists(reserved)).order_by("pk")[:500]:
        if row.member_id not in members:
            notify_join_followup(row)
            count += 1
    return count


def register():
    register_source(SOURCE, NotificationSource(_eligible, lambda envelope: _content(_load(envelope))))
