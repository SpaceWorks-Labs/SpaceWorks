"""Audit presentation for lane L21a: review stages, attendance, re-accept, crew, check-in lists.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read
time, so these entries name the action only. Answers, scores, notes and dietary needs are
never written to an audit row in any case.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.admission_stage.created", gettext_noop("Review stage added")),
    P("event.admission_stage.updated", gettext_noop("Review stage changed")),
    P("event.admission_stage.panel_changed", gettext_noop("Review stage panel changed")),
    P("event.admission_stage.assigned", gettext_noop("Reviewers assigned to a stage")),
    P("event.admission_stage.review_submitted", gettext_noop("Stage review submitted")),
    P("event.admission_stage.review_recused", gettext_noop("Stage reviewer recused")),
    P("event.application.stage_advanced", gettext_noop("Application advanced to the next stage")),
    P("event.application.decision_skipped", gettext_noop("Stale application decision skipped")),
    P("event.attendance.sent", gettext_noop("Attendance confirmation sent")),
    P("event.attendance.replied", gettext_noop("Attendance reply received")),
    P("event.participation_settings_updated", gettext_noop("Event participation switches changed")),
    P("event.crew.signed_up", gettext_noop("Crew sign-up received")),
    P("event.crew.approved", gettext_noop("Crew member approved")),
    P("event.crew.declined", gettext_noop("Crew sign-up declined")),
    P("event.crew.withdrawn", gettext_noop("Crew member withdrew")),
    P("event.crew.removed", gettext_noop("Crew member removed")),
    P("event.crew.place_created", gettext_noop("Crew place given")),
    P("event.crew.place_released", gettext_noop("Crew place released")),
    P("event.checkin_list.created", gettext_noop("Check-in list created")),
    P("event.checkin_list.updated", gettext_noop("Check-in list changed")),
    P("event.checkin_list.archived", gettext_noop("Check-in list archived")),
    P("event.checkin_list.scanned", gettext_noop("Collected from a check-in list")),
)
