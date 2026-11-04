"""Audit presentation for lane L21a: review stages, attendance, re-accept, crew, check-in lists.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read
time, so these entries name the action only. Answers, scores, notes and dietary needs are
never written to an audit row in any case.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.admission_stage.created", "Review stage added"),
    P("event.admission_stage.updated", "Review stage changed"),
    P("event.admission_stage.panel_changed", "Review stage panel changed"),
    P("event.admission_stage.assigned", "Reviewers assigned to a stage"),
    P("event.admission_stage.review_submitted", "Stage review submitted"),
    P("event.admission_stage.review_recused", "Stage reviewer recused"),
    P("event.application.stage_advanced", "Application advanced to the next stage"),
    P("event.application.decision_skipped", "Stale application decision skipped"),
    P("event.attendance.sent", "Attendance confirmation sent"),
    P("event.attendance.replied", "Attendance reply received"),
    P("event.participation_settings_updated", "Event participation switches changed"),
    P("event.crew.signed_up", "Crew sign-up received"),
    P("event.crew.approved", "Crew member approved"),
    P("event.crew.declined", "Crew sign-up declined"),
    P("event.crew.withdrawn", "Crew member withdrew"),
    P("event.crew.removed", "Crew member removed"),
    P("event.crew.place_created", "Crew place given"),
    P("event.crew.place_released", "Crew place released"),
    P("event.checkin_list.created", "Check-in list created"),
    P("event.checkin_list.updated", "Check-in list changed"),
    P("event.checkin_list.archived", "Check-in list archived"),
    P("event.checkin_list.scanned", "Collected from a check-in list"),
)
