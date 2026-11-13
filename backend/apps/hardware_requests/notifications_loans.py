"""Loan-depth notices (L12): request withdrawn/expired, and a waitlist offer.

Same durable fan-out as every hardware notice; bodies are built here because they
carry no editable template yet. Bearer links are never content: the member link
opens the authenticated member page.
"""
from django.utils.translation import gettext, gettext_noop

from apps.accounts import rbac
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.local_time import to_local

from .notifications_p2 import fanout, revision, safe_adapter

WAITLIST_KIND = "hardware.waitlist"
_CLOSED = {
    "cancelled": (gettext_noop("request withdrawn"), gettext_noop("was withdrawn. Any reserved items are free again.")),
    "expired": (gettext_noop("reservation expired"),
                gettext_noop("was not collected in time, so the reservation has been released.")),
}


@safe_adapter
def notify_closed(row, event):
    from .notifications_p2_requests import KIND, request_revision
    title, sentence = (gettext(part) for part in _CLOSED[event])
    link = local_link(row.makerspace, "member")
    own = {"subject": gettext("%(space)s %(title)s") % {"space": row.makerspace.name, "title": title},
           "text": gettext("Your request #%(id)s %(sentence)s") % {"id": row.pk, "sentence": sentence},
           "html": "", "link": link}
    staff = {"subject": gettext("Hardware request #%(id)s %(title)s") % {"id": row.pk, "title": title},
             "text": gettext("Hardware request #%(id)s %(sentence)s") % {"id": row.pk, "sentence": sentence}}
    owner = row.requester if not row.anonymous_idempotency_key_fingerprint else None
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware", event=event,
                  kind=KIND, source=row.pk, version=request_revision(row), subject=row, owner=owner,
                  own=own, staff=staff, context={"request_id": row.pk})


def _entry_revision(entry):
    return revision(entry.status, entry.offered_at, entry.offer_expires_at)


@safe_adapter
def notify_waitlist_offer(entry):
    space = entry.makerspace
    until = to_local(space, entry.offer_expires_at).strftime("%Y-%m-%d %H:%M %Z")
    own = {"subject": gettext("%(space)s: your waitlisted item is ready") % {"space": space.name},
           "text": gettext("%(item)s is free and held for you until %(until)s. "
                           "Request it from your member page before then.") % {"item": entry.product.name, "until": until},
           "html": "", "link": local_link(space, "member")}
    return fanout(space=space, feature="hardware_requests", stream="hardware", event="waitlist_offer",
                  kind=WAITLIST_KIND, source=entry.pk, version=_entry_revision(entry), subject=entry,
                  owner=entry.user, own=own, context={"entry_id": entry.pk})


def eligible_waitlist(envelope):
    from .models_loans import LoanWaitlistEntry
    entry = rbac.scope_notification_policy(LoanWaitlistEntry.objects.all(),
                                           makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    return bool(entry and entry.status == "offered" and envelope.audience == "requester"
                and entry.user_id == envelope.recipient_id and _entry_revision(entry) == envelope.revision)


RENEWAL_KIND = "hardware.renewal"
ACTIVE_LOANS = ("issued", "partially_returned")


def _renewal_revision(row):
    return revision(row.pk, row.renewal_count, row.return_due_at)


@safe_adapter
def notify_renewed(row, *, by_staff):
    """Decision 221(f): the borrower hears the new due date; staff hear of a self-renewal only."""
    space = row.makerspace
    due = to_local(space, row.return_due_at).strftime("%Y-%m-%d %H:%M %Z")
    own = {"subject": gettext("%(space)s: loan #%(id)s renewed") % {"space": space.name, "id": row.pk},
           "text": gettext("Your loan #%(id)s was renewed. The new return date is %(due)s.") % {"id": row.pk, "due": due},
           "html": "", "link": local_link(space, "member")}
    staff = None if by_staff else {
        "subject": gettext("Loan #%(id)s renewed") % {"id": row.pk},
        "text": gettext("Hardware request #%(id)s was renewed by its borrower until %(due)s.") % {"id": row.pk, "due": due}}
    owner = row.requester if not row.anonymous_idempotency_key_fingerprint else None
    return fanout(space=space, feature="hardware_requests", stream="hardware", event="renewed",
                  kind=RENEWAL_KIND, source=row.pk, version=_renewal_revision(row), subject=row, owner=owner,
                  own=own, staff=staff, rooms=False,
                  context={"request_id": row.pk, "due_at": row.return_due_at.isoformat()})


def eligible_renewal(envelope):
    from .models import HardwareRequest
    row = rbac.scope_notification_policy(HardwareRequest.objects.all(),
                                         makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if row is None or row.status not in ACTIVE_LOANS or row.return_due_at is None:
        return False
    if _renewal_revision(row) != envelope.revision:
        return False  # renewed again (a newer notice carries the newer date) or returned
    if envelope.audience == "requester":
        return row.requester_id == envelope.recipient_id and not row.anonymous_idempotency_key_fingerprint
    return envelope.audience == "staff"


def register():
    register_source(WAITLIST_KIND, NotificationSource(eligible_waitlist))
    register_source(RENEWAL_KIND, NotificationSource(eligible_renewal))
    from .pickup_reminders import register as register_pickup
    register_pickup()
