"""Release-2 L4 notices: the manual renewal reminder and the erasure decision.

Both reserve their intent inside the domain transaction (`fanout`) and re-check
eligibility at send time, like every Phase-2 adapter:

* `membership.renewal_desk` / `renewal_due` -- staff nudged this member from the renewal
  desk. The revision is the term plus the local day, so one member gets at most one
  manual reminder a day however many times staff click.
* `membership.erasure` / `erasure_approved` | `erasure_rejected` -- the decision on a
  member's per-space erasure request, to that member only.
"""
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import fanout, revision, safe_notification, scoped, template

from .models import MembershipErasureRequest, MembershipTerm
from .platform import feature_enabled

REMINDER_SOURCE = "membership.renewal_desk"
ERASURE_SOURCE = "membership.erasure"
ERASURE_EVENTS = {"erasure_approved", "erasure_rejected"}


def _load_term(envelope):
    return scoped(MembershipTerm, envelope.makerspace_id, field="membership__makerspace_id").select_related(
        "membership__makerspace", "membership__user", "plan").filter(pk=envelope.source_id).first()


def _term_body(term):
    space = term.membership.makerspace
    return template(space, "membership", "requester", "renewal_due",
                    {"makerspace": bag(name=space.name), "event_name": "renewal_due",
                     "subject": bag(id=term.membership_id, status=term.status)}, link=local_link(space, "member"))


def _reminder_eligible(envelope):
    term = _load_term(envelope)
    if term is None or envelope.event != "renewal_due" or term.status == "cancelled":
        return False
    membership = term.membership
    if (membership.user_id != envelope.recipient_id or membership.status != "active"
            or not feature_enabled(membership.makerspace, "membership.renewal_desk")
            or MembershipTerm.objects.filter(renewed_from=term).exists()):
        return False
    return envelope.revision == revision(term.pk, envelope.context.get("day", ""))


@safe_notification
def notify_renewal_reminder(term, day):
    space = term.membership.makerspace
    return fanout(row=term, space=space, feature="members", stream="membership", event="renewal_due",
                  source_kind=REMINDER_SOURCE, revision=revision(term.pk, day.isoformat()),
                  owner=term.membership.user, owner_body=_term_body(term), staff=False,
                  context={"day": day.isoformat()},
                  owner_context={"subject": bag(id=term.membership_id, status=term.status)})


def _load_erasure(envelope):
    return scoped(MembershipErasureRequest, envelope.makerspace_id).select_related(
        "makerspace", "membership__user").filter(pk=envelope.source_id).first()


def _erasure_body(row, event):
    space = row.makerspace
    return template(space, "membership", "requester", event,
                    {"makerspace": bag(name=space.name), "event_name": event,
                     "subject": bag(id=row.pk, status=row.status), "decision": bag(note=row.decision_note)},
                    link=local_link(space, "member"))


def _erasure_eligible(envelope):
    row = _load_erasure(envelope)
    if row is None or envelope.event not in ERASURE_EVENTS or row.membership.user_id != envelope.recipient_id:
        return False
    expected = "erasure_approved" if row.status == row.Status.APPROVED else "erasure_rejected"
    return envelope.event == expected and envelope.revision == revision(row.pk, row.status)


@safe_notification
def notify_erasure_decision(row):
    event = "erasure_approved" if row.status == row.Status.APPROVED else "erasure_rejected"
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event=event,
                  source_kind=ERASURE_SOURCE, revision=revision(row.pk, row.status),
                  owner=row.membership.user, owner_body=_erasure_body(row, event), staff=False,
                  owner_context={"subject": bag(id=row.pk, status=row.status)})


def register():
    register_source(REMINDER_SOURCE, NotificationSource(_reminder_eligible,
                                                        lambda envelope: _term_body(_load_term(envelope))))
    register_source(ERASURE_SOURCE, NotificationSource(
        _erasure_eligible, lambda envelope: _erasure_body(_load_erasure(envelope), envelope.event)))
