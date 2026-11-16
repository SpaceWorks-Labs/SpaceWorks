"""Job-flow notices (#141): every new lifecycle edge, reminders and the no-show flag.

Same durable fan-out and channel resolver as every machine-service notice (the
`printing` notification category). Member legs go to the job's owner only; staff legs
to people who can manage that machine type. Contents carry no bearer link and no pickup
code -- the member reads the code in their member area.
"""

from django.utils.translation import gettext, gettext_noop

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.platform import module_enabled

from .models import MachineServiceRequest

KIND = "machines.job"
OWNER_ONLY = {"quote_reminder", "pickup_reminder"}
STAFF_ONLY = {"resubmitted", "quote_declined", "no_show_flagged"}
COPY = {
    "changes_requested": gettext_noop("needs changes before it can go ahead. See what to change in your member area."),
    "resubmitted": gettext_noop("was resubmitted by the member and is ready for review."),
    "quoted": gettext_noop("has a quote waiting for your approval."),
    "quote_reminder": gettext_noop("still has a quote waiting for you; it expires soon."),
    "quote_approved": gettext_noop("quote was approved."),
    "quote_declined": gettext_noop("quote was declined by the member."),
    "quote_expired": gettext_noop("quote expired without an answer, so the job was cancelled."),
    "requeued": gettext_noop("failed and was put back at the front of the queue, at no charge."),
    "pickup_reminder": gettext_noop("is ready and waiting for you to collect it."),
    "uncollected": gettext_noop("was not collected in time and is now the space's to recycle."),
    "no_show_flagged": gettext_noop("belongs to a member who has not collected three jobs in six months."),
}
EVENTS = frozenset(COPY)


def _version(row, event):
    return revision(event, row.status, row.updated_at, row.quoted_at, row.pickup_reminders_sent)


def eligible(envelope):
    row = rbac.scope_notification_policy(MachineServiceRequest.objects.all(),
                                         makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if row is None or _version(row, envelope.event) != envelope.revision:
        return False
    if not module_enabled(envelope.makerspace, "machine_service"):
        return False
    if envelope.audience == "requester":
        from apps.hardware_requests.notifications_p2_email import source_ready
        return envelope.recipient_id == (row.member_id or row.requester_id) and source_ready(envelope)
    if envelope.recipient_id:
        from apps.accounts.models import User

        from . import access
        from .job_rules import machine_type_of
        recipient = User.objects.filter(pk=envelope.recipient_id).first()
        return recipient is not None and access.can_create_machine(recipient, row.makerspace_id, machine_type_of(row))
    return True


@safe_adapter
def notify_job(row, event):
    if event not in EVENTS:
        raise ValueError("Unknown machine job event")
    from .notifications_p2_service import scope_for
    values = {"id": row.pk, "sentence": gettext(COPY[event])}
    own = None if event in STAFF_ONLY else {
        "subject": gettext("Your job #%(id)s") % values, "text": gettext("Your job #%(id)s %(sentence)s") % values,
        "link": local_link(row.makerspace, "member")}
    staff = None if event in OWNER_ONLY else {
        "subject": gettext("Machine job #%(id)s") % values, "text": gettext("Machine job #%(id)s %(sentence)s") % values}
    return fanout(space=row.makerspace, feature="printing", stream="printing", event=event, kind=KIND,
                  source=row.pk, version=_version(row, event), subject=row,
                  owner=(row.member or row.requester) if own else None, own=own, staff=staff,
                  rooms=staff is not None, scope=scope_for(row), context={"machine_service_request_id": row.pk})


def flag_no_shows(row):
    """#142 OQ-7: the third uncollected job in six months flags the member to staff (no ban)."""
    from datetime import timedelta

    from django.utils import timezone

    from .job_policy import NO_SHOW_LIMIT, NO_SHOW_WINDOW_DAYS
    if row.member_id is None:
        return None
    count = MachineServiceRequest.objects.filter(
        makerspace_id=row.makerspace_id, member_id=row.member_id, status=MachineServiceRequest.Status.UNCOLLECTED,
        uncollected_at__gte=timezone.now() - timedelta(days=NO_SHOW_WINDOW_DAYS)).count()
    if count == NO_SHOW_LIMIT:
        return notify_job(row, "no_show_flagged")
    return None


def register():
    register_source(KIND, NotificationSource(eligible))
