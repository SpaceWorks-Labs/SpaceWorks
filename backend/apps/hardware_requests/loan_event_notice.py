"""Event context for lending notices (decision 221b): "for <event>" on event-linked loans.

An event-linked loan notice is its own kind (open item B11): the context carries
`notice_kind="event_loan"` with the event title, window and staff desk link, and the text names
the window and desk. The lifecycle (issued, returned, due, overdue) stays the notice's own `event`.

The core request never imports events. The link is read lazily, and only while the Events
module is installed and on for the space; a non-event loan returns None and its notice is
byte-identical to before.
"""
from django.apps import apps
from django.utils.translation import gettext


def loan_event(row):
    """`{"id", "title", "starts_at", "ends_at", "desk_link"}` of the live event a request is linked to, or None."""
    if not isinstance(row, _request_model()) or not apps.is_installed("apps.events"):
        return None
    from apps.makerspaces.platform import module_enabled
    if not module_enabled(row.makerspace, "events"):
        return None
    from apps.events.models_loan_context import EventLoanContext
    found = EventLoanContext.objects.filter(
        request_id=row.pk, makerspace_id=row.makerspace_id, active=True,
        event__makerspace_id=row.makerspace_id,
    ).values_list("event_id", "event__title", "event__starts_at", "event__ends_at").first()
    if not found:
        return None
    return {"id": found[0], "title": found[1], "starts_at": found[2], "ends_at": found[3],
            "desk_link": f"/admin/events/{found[0]}"}


def context_for(event):
    """Machine-readable event fields every event-linked loan envelope carries."""
    return {"notice_kind": "event_loan", "event_id": event["id"], "event_title": event["title"],
            "event_starts_at": event["starts_at"].isoformat() if event.get("starts_at") else "",
            "event_ends_at": event["ends_at"].isoformat() if event.get("ends_at") else "",
            "event_desk_link": event.get("desk_link", "")}


def _request_model():
    from .models import HardwareRequest
    return HardwareRequest


def annotate(rendered, event):
    """Return `rendered` with the event title in its subject and a closing line in its text."""
    if not rendered or not event:
        return rendered
    out = dict(rendered)
    title = event["title"]
    out["subject"] = (out.get("subject", "") + " " + gettext("(for %(title)s)") % {"title": title}).strip()
    window = ""
    if event.get("starts_at") and event.get("ends_at"):
        from django.utils import timezone
        start, end = (timezone.localtime(event[key]).strftime("%Y-%m-%d %H:%M") for key in ("starts_at", "ends_at"))
        window = gettext("Event window: %(start)s to %(end)s") % {"start": start, "end": end}
    lines = [out.get("text", "").rstrip(), "", gettext("For event: %(title)s") % {"title": title}] + ([window] if window else [])
    out["text"] = "\n".join(lines)
    if out.get("html"):
        from django.utils.html import escape
        out["html"] = f"{out['html']}<p>" + escape(gettext("For event: %(title)s") % {"title": title}) + "</p>" + (f"<p>{escape(window)}</p>" if window else "")
    if event.get("desk_link") and "link" in out:
        out["link"] = out["link"] or event["desk_link"]
    return out
