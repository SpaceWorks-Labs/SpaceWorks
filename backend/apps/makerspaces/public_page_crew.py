"""The public crew section on an event's Pages page (release 2, #128 C-36).

The organiser adds the section; it lists only approved crew who chose to be shown and
hold a live public profile in the event's space (#25): handle, display name and crew
role, nothing else. It renders nothing while `events.crew` is off or Events is removed.
"""


def crew_section(kind, owner, title):
    from apps.separability.registry import runtime_active
    if kind != "event" or not runtime_active("events"):
        return None
    from apps.events.models import Event
    if not isinstance(owner, Event):
        return None  # a series page has no single crew
    from .platform import feature_enabled
    if not feature_enabled(owner.makerspace, "events.crew"):
        return None
    from apps.events.contributions.crew_reads import public_crew
    cards = public_crew(owner, require_switch=False)
    return {"title": title, "results": cards} if cards else None
