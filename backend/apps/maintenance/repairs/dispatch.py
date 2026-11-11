"""Send an issue to the technicians staff picked (#98, C-4): notify only.

Staff tick one or several technicians (the area's defaults come pre-ticked). Each one is
sent the issue over email plus every chat channel they chose AND opted in to; asking
for a channel without consent refuses the whole send (`technician_no_consent`) before
anything goes out. Every single send is an append-only `TechnicianDispatch` row
(delivered / failed, provider message id) shown on the issue history. The technicians
are assigned to the issue; an in-house Technician then sees it under "My jobs".
"""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from apps.integrations.fanout_jobs import defer_enabled, maybe_defer, register

from . import areas, channels, errors, history
from .notify import subject_label
from .services_issues import _expect, _require_manager

MAX_CONTACTS = 10


def _plan(contacts, requested):
    plan = []
    for contact in contacts:
        wanted = requested if requested is not None else [
            channel for channel in (contact.channels or ["email"]) if channel == "email"
            or channels.consented(contact, channel)]
        wanted = list(dict.fromkeys(["email", *wanted])) if channels.consented(contact, "email") else wanted
        missing = [channel for channel in wanted if not channels.consented(contact, channel)]
        if missing or not wanted:
            raise errors.no_consent(f"{contact.name} has not opted in to {', '.join(missing) or 'any channel'}.")
        plan.append((contact, wanted))
    return plan


def message(issue, note=""):
    space = issue.makerspace
    lines = [f"Repair request from {space.name} (issue #{issue.pk})", "",
             f"What: {subject_label(issue)} ({issue.get_area_display().lower()})",
             f"Problem: {issue.title}", "", issue.description[:1500]]
    if note:
        lines += ["", f"Note from the space: {str(note)[:500]}"]
    lines += ["", f"Please reply to {space.name} directly to arrange a visit."]
    return "\n".join(lines)


def send_planned(actor, issue, *, contact_ids, channel_names=None, note=""):
    """Validate, send over every planned channel, record the append-only rows. Runs in the Celery worker
    (or inline where none exists): provider calls never block the staff request."""
    from apps.maintenance.models import IssueAssignment, TechnicianContact, TechnicianDispatch
    if not isinstance(contact_ids, list) or not contact_ids or len(contact_ids) > MAX_CONTACTS:
        raise ValidationError({"contact_ids": gettext('Pick one to {MAX_CONTACTS} technicians.').format(MAX_CONTACTS=MAX_CONTACTS)})
    if channel_names is not None and (not isinstance(channel_names, list)
                                      or set(channel_names) - {"email", "telegram", "whatsapp", "sms"}):
        raise ValidationError({"channels": gettext("Choose email, Telegram, WhatsApp or SMS.")})
    with transaction.atomic():
        issue = history.lock(issue)
        _require_manager(actor, issue)
        areas.require(issue.makerspace, areas.REPAIRS[issue.area])
        _expect(issue, "triaged", "assigned", "in_progress")
        contacts = list(TechnicianContact.objects.select_related("person").filter(
            makerspace_id=issue.makerspace_id, pk__in=contact_ids, is_archived=False))
        if len(contacts) != len(set(contact_ids)):
            raise ValidationError({"contact_ids": gettext("Choose technicians of this makerspace.")})
        plan = _plan(contacts, channel_names)
        text, subject = message(issue, note), f"Repair request: {issue.title}"
        rows = []
        for contact, wanted in plan:
            IssueAssignment.objects.get_or_create(issue=issue, contact=contact)
            for channel in wanted:
                with transaction.atomic():
                    outcome = channels.send(issue.makerspace, contact, channel, subject, text,
                                            f"repair-{issue.pk}-{contact.pk}-{channel}")
                rows.append(TechnicianDispatch.objects.create(
                    issue=issue, contact=contact, channel=channel, sent_by=actor,
                    status="delivered" if outcome.delivered else "failed", failure_code=outcome.failure_code,
                    provider_message_id=outcome.message_id))
            history.step(issue, "dispatched", actor, "dispatch.sent", contact=contact, note=note, meta={
                "contact_id": contact.pk, "channels": wanted,
                "delivered": sum(1 for row in rows if row.contact_id == contact.pk and row.status == "delivered")})
        if issue.state == "triaged":
            issue.state = "assigned"
            issue.save(update_fields=["state", "updated_at"])
        audit.record(actor, "issue.dispatched", makerspace=issue.makerspace, target=issue, meta={
            "issue_id": issue.pk, "machine_id": issue.machine_id, "contacts": len(plan), "sends": len(rows),
            "failed": sum(1 for row in rows if row.status == "failed")})
    return rows


register(send_planned)


def dispatch(actor, issue, *, contact_ids, channel_names=None, note=""):
    """Request entry: refuse a bad send immediately, then hand the sending to a worker job (ids only)."""
    if not defer_enabled():
        return send_planned(actor, issue, contact_ids=contact_ids, channel_names=channel_names, note=note)
    from apps.maintenance.models import TechnicianContact
    if not isinstance(contact_ids, list) or not contact_ids or len(contact_ids) > MAX_CONTACTS:
        raise ValidationError({"contact_ids": gettext('Pick one to {MAX_CONTACTS} technicians.').format(MAX_CONTACTS=MAX_CONTACTS)})
    with transaction.atomic():  # permission, area, state and consent errors surface here, not in the worker
        locked = history.lock(issue)
        _require_manager(actor, locked)
        areas.require(locked.makerspace, areas.REPAIRS[locked.area])
        _expect(locked, "triaged", "assigned", "in_progress")
        contacts = list(TechnicianContact.objects.select_related("person").filter(
            makerspace_id=locked.makerspace_id, pk__in=contact_ids, is_archived=False))
        if len(contacts) != len(set(contact_ids)):
            raise ValidationError({"contact_ids": gettext("Choose technicians of this makerspace.")})
        _plan(contacts, channel_names)
        if maybe_defer(send_planned, (actor, locked), {"contact_ids": contact_ids, "channel_names": channel_names,
                                                       "note": note}, feature="maintenance", event="repair_dispatch"):
            return []
    return send_planned(actor, issue, contact_ids=contact_ids, channel_names=channel_names, note=note)
