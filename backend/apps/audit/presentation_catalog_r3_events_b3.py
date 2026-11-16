"""Audit presentation for parity E-B3: team moderation and crew edits."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.hackathon.team_leadership_transferred", gettext_noop("Team leadership handed over")),
    P("event.hackathon.team_member_removed", gettext_noop("Team member removed")),
    P("event.hackathon.team_join_declined", gettext_noop("Team join request declined")),
    P("event.hackathon.team_leave_cancelled_registration", gettext_noop("Team member left and cancelled their place")),
    P("event.hackathon.team_renamed_by_staff", gettext_noop("Team renamed by an organiser")),
    P("event.hackathon.team_member_moved", gettext_noop("Team member moved by an organiser")),
    P("event.hackathon.team_deleted", gettext_noop("Team deleted by an organiser")),
    P("event.hackathon.team_restored", gettext_noop("Team restored after a delete")),
    P("event.crew.updated", gettext_noop("Crew member edited")),
    P("event.crew.reordered", gettext_noop("Crew order changed")),
)
