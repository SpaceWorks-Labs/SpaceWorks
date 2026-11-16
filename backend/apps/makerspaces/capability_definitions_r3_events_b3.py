"""Parity E-B3: team moderation and crew kinds (both ON by default once Events and its parent feature are on).

* `events.team_moderation` -- a team leader hands the team over, removes a member or leaves and cancels the
  registration; organisers rename a team, move a member and delete a team with a five-minute undo.
  Requires `events.hackathons`. Off = those routes answer 404; the data is kept.
* `events.crew_kinds` -- a crew kind (organiser, volunteer, mentor, judge) beside the free role label: it
  shows on the roster, the public crew section and the badge chip, and can be filtered. Requires `events.crew`.
"""


def definitions(feature):
    return (
        feature("events.team_moderation", "events", "Team handover and moderation",
                "Team leaders hand over leadership and remove members; organisers rename teams, move members "
                "and delete a team with a five-minute undo.",
                default_enabled=True, requires_features=("events.hackathons",)),
        feature("events.crew_kinds", "events", "Crew kinds",
                "Tag each crew member as organiser, volunteer, mentor or judge; the kind shows on the crew "
                "list, the public crew section and the crew badge.",
                default_enabled=True, requires_features=("events.crew",)),
    )
