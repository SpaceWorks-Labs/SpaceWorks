"""Readable wording for a notification's lifecycle key inside rendered template text.

Contexts carry the machine key as ``event_name`` (templates compare it, e.g.
``{% if event_name == "restored" %}``); message prose shows ``event_label`` instead,
so a member reads "payment due today" rather than ``payment_due_today``.
"""


def event_label(key):
    return str(key or "").replace("_", " ").strip()


def with_event_label(context):
    if "event_name" in context and "event_label" not in context:
        return {**context, "event_label": event_label(context["event_name"])}
    return context
