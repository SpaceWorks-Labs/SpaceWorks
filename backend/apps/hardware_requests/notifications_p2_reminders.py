"""Loan ladder reminders keep mandatory mail alongside selected private channels."""
from datetime import timezone as datetime_timezone

from django.utils import timezone
from django.utils.html import escape

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.integrations.email_templates import hardware_context, render
from apps.integrations.email_templates_registry import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from .models import HardwareRequest
from .notifications_p2 import content, fanout, revision

KIND = "hardware.loan_reminder"


def eligible(envelope):
    from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
    from .loan_reminders import _offsets
    row = rbac.scope_for_scheduled_work(HardwareRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id,
        status__in=["issued", "partially_returned"]).first()
    if row is None or row.return_due_at is None:
        return False
    policy = rbac.scope_for_scheduled_work(MakerspaceLoanPolicy.objects.all(),
        makerspace_id=envelope.makerspace_id).first()
    context = envelope.context
    if policy is None or context["offset_seconds"] not in _offsets(policy, context["kind"]):
        return False
    if row.return_due_at.isoformat() != context["due_at"]:
        return False
    if envelope.audience == "requester":
        return row.requester_id == envelope.recipient_id and not row.anonymous_idempotency_key_fingerprint
    return context["kind"] == "escalation"


@safe_adapter
def deliver(makerspace, loan, reminder, message, local_tz):
    staff = reminder.kind == "escalation"
    context = hardware_context(loan, staff=staff)
    values = {key: value for key, value in vars(context["request"]).items() if key != "_frozen"}
    due = loan.return_due_at.astimezone(local_tz)
    values["return_due_at"] = due.replace(tzinfo=datetime_timezone(due.utcoffset(), due.tzname()))
    context["request"] = bag(**values)
    context["now"] = timezone.now().astimezone(local_tz)
    if staff:
        context["staff_summary"] = message.body
    with timezone.override(local_tz):
        rendered = render(makerspace, "hardware", "staff" if staff else "requester",
                          "return_reminder", context, use_tz=False)
    if not staff:
        rendered["text_body"] += "\n\n" + message.body
        rendered["html_body"] += f"<p>{escape(message.body)}</p>"
    version = revision(loan.return_due_at, reminder.kind, reminder.offset_seconds)
    return fanout(space=makerspace, feature="hardware_requests", stream="hardware",
        event="overdue_escalated" if staff else "return_reminder", kind=KIND,
        source=loan.pk, version=version, subject=loan,
        owner=None if staff else loan.requester, own=None if staff else content(rendered,
            link=local_link(makerspace, "member")), staff=content(rendered) if staff else None,
        staff_context=context if staff else None,
        context={"due_at": loan.return_due_at.isoformat(), "kind": reminder.kind,
                 "offset_seconds": reminder.offset_seconds})


def register():
    register_source(KIND, NotificationSource(eligible))
