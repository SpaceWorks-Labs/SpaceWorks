"""Query-free registration manifest; each domain still owns live source policy."""
from apps.integrations.notification_sources import NotificationSource, register_source

SOURCE_OWNERS = {
    "events.application": "A", "events.answer_date": "P", "events.team": "A", "events.team_invite": "A",
    "events.submission": "B", "events.mentor_help": "C", "events.contributor": "C",
    "events.role_assignment": "C", "events.judging": "D", "events.certificate": "E",
}


def register_programme_sources(registrations):
    """G passes lane-owned NotificationSource objects at EventsConfig.ready().

    Registration does not invent permissive defaults. Missing sources stay refused
    by the always-present shared transport, including retry and digest rebuild.
    """
    seen = set()
    for kind, source in registrations:
        if kind not in SOURCE_OWNERS or kind in seen or not isinstance(source, NotificationSource):
            raise ValueError("Unknown, duplicate or untyped programme notification source.")
        if not callable(source.eligible):
            raise ValueError("A live source predicate is required.")
        seen.add(kind)
        register_source(kind, source)
    return frozenset(seen)


def missing_programme_sources(registrations):
    """Integration diagnostic over names only; never queries tenant or member data."""
    return tuple(sorted(set(SOURCE_OWNERS) - set(registrations)))
