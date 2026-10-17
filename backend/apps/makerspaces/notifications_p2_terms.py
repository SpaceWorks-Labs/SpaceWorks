"""Renewal notices reserve an intent alongside the term/claim mutation."""
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.integrations.email_templates_registry_helpers import bag
from apps.operations.notifications_p2 import fanout, revision, safe_notification, scoped, template
from .models import MembershipTerm
from .platform import feature_enabled

SOURCE = "membership.term"
EVENTS = {"renewal_due", "lapsed", "renewal_failed", "renewed", "grace_started"}


def term_revision(term, event, reminder=None):
    return revision(term.pk, term.starts_at, term.ends_at,
                    term.renewal_attempts if event == "renewal_failed" else None,
                    reminder.pk if reminder else None)


def load(envelope):
    return scoped(MembershipTerm, envelope.makerspace_id, field="membership__makerspace_id").select_related(
        "membership__makerspace", "membership__user", "plan",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    term = load(envelope)
    if term is None or envelope.event not in EVENTS:
        return False
    membership = term.membership
    if (membership.user_id != envelope.recipient_id or membership.status != "active"
            or not feature_enabled(membership.makerspace, "membership.lifecycle_mail")):
        return False
    if term.status == "cancelled":
        return False
    from .membership_renewals import grace_end
    now = timezone.now()
    if envelope.event == "lapsed" and now < grace_end(term):
        return False
    if envelope.event == "grace_started" and not term.ends_at <= now < grace_end(term):
        return False
    if envelope.event == "renewed" and (not term.renewed_from_id or term.ends_at <= now):
        return False
    if envelope.event == "renewal_failed" and term.renewal_attempts == 0:
        return False
    if envelope.event != "renewed" and (membership.renewal_cancelled_at or MembershipTerm.objects.filter(renewed_from=term).exists()):
        return False
    if envelope.event == "renewal_failed" and term.renewal_payment_id:
        from apps.payments.models import Payment
        if scoped(Payment, membership.makerspace_id).filter(pk=term.renewal_payment_id).exclude(status="pending").exists():
            return False
    reminder = None
    if envelope.context.get("reminder_id"):
        from apps.operations.models_reminders import ReminderSchedule
        from .membership_renewal_reminders import _current
        reminder = scoped(ReminderSchedule, membership.makerspace_id).filter(
            pk=envelope.context["reminder_id"], source="membership.renewal",
        ).first()
        if reminder is None or _current(membership.makerspace, reminder, timezone.now()) is None:
            return False
    return envelope.revision == term_revision(term, envelope.event, reminder)


def term_body(term, event):
    space = term.membership.makerspace
    return template(space, "membership", "requester", event,
        {"makerspace": bag(name=space.name), "event_name": event,
         "subject": bag(id=term.membership_id, status=term.status)}, link=local_link(space, "member"))


def render(envelope):
    return term_body(load(envelope), envelope.event)


@safe_notification
def notify_term(term, event, *, reminder=None):
    space = term.membership.makerspace
    if event not in EVENTS:
        raise ValueError("Unknown membership term event")
    if not feature_enabled(space, "membership.lifecycle_mail"):
        return
    return fanout(row=term, space=space, feature="members", stream="membership", event=event,
        source_kind=SOURCE, revision=term_revision(term, event, reminder), owner=term.membership.user,
        owner_body=term_body(term, event), staff=False, context={"reminder_id": reminder.pk if reminder else None})


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
