"""Parity E-B7: discovery filters and space insights (both ON by default once Events is on).

* `events.discovery_filters` -- public discovery (`/discover`) can be narrowed by tag and by organiser, and the
  search also matches tags and organiser names. Off = the extra filters are ignored and search stays on
  title, location and description.
* `events.space_insights` -- the top-events and returning-attendee insight for a space or an organisation's
  hosted events. Off = those routes answer 404; the data is kept.
"""


def definitions(feature):
    return (
        feature("events.discovery_filters", "events", "Discovery tag and organiser filters",
                "Visitors narrow public event discovery by tag or organiser, and search also finds tags "
                "and organiser names.",
                default_enabled=True),
        feature("events.space_insights", "events", "Event insights",
                "Top events over six months and the share of returning attendees for a space or an "
                "organisation's hosted events; small groups are suppressed.",
                default_enabled=True),
    )
