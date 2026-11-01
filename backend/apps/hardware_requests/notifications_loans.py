"""Loan-depth notices (L12): request withdrawn/expired, and a waitlist offer.

Same durable fan-out as every hardware notice; bodies are built here because they
carry no editable template yet. Bearer links are never content: the member link
opens the authenticated member page.
"""
from apps.accounts import rbac
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source

from .notifications_p2 import fanout, revision, safe_adapter

WAITLIST_KIND = "hardware.waitlist"
_CLOSED = {
    "cancelled": ("request withdrawn", "was withdrawn. Any reserved items are free again."),
    "expired": ("reservation expired", "was not collected in time, so the reservation has been released."),
}


@safe_adapter
def notify_closed(row, event):
    from .notifications_p2_requests import KIND, request_revision
    title, sentence = _CLOSED[event]
    link = local_link(row.makerspace, "member")
    own = {"subject": f"{row.makerspace.name} {title}", "text": f"Your request #{row.pk} {sentence}",
           "html": "", "link": link}
    staff = {"subject": f"Hardware request #{row.pk} {title}", "text": f"Hardware request #{row.pk} {sentence}"}
    owner = row.requester if not row.anonymous_idempotency_key_fingerprint else None
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware", event=event,
                  kind=KIND, source=row.pk, version=request_revision(row), subject=row, owner=owner,
                  own=own, staff=staff, context={"request_id": row.pk})


def _entry_revision(entry):
    return revision(entry.status, entry.offered_at, entry.offer_expires_at)


@safe_adapter
def notify_waitlist_offer(entry):
    space = entry.makerspace
    until = entry.offer_expires_at.strftime("%Y-%m-%d %H:%M UTC")
    own = {"subject": f"{space.name}: your waitlisted item is ready",
           "text": (f"{entry.product.name} is free and held for you until {until}. "
                    "Request it from your member page before then."),
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


def register():
    register_source(WAITLIST_KIND, NotificationSource(eligible_waitlist))
