"""Audit metadata IDs written by release-2 lane L21a (review stages, attendance, crew, check-in lists)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_STAGE = tuple(f"event.admission_stage.{action}" for action in (
    "created", "updated", "panel_changed", "assigned", "review_submitted", "review_recused"))
_CREW = tuple(f"event.crew.{action}" for action in (
    "signed_up", "approved", "declined", "withdrawn", "removed", "place_created", "place_released"))
_LISTS = tuple(f"event.checkin_list.{action}" for action in ("created", "updated", "archived", "scanned"))
_APPLICATION = ("event.application.stage_advanced", "event.application.decision_skipped")

EDGES = {
    **_remap("events.Event", *((action, "event_id") for action in (
        *_STAGE, *_CREW, *_LISTS, *_APPLICATION, "event.attendance.sent", "event.attendance.replied",
        "event.participation_settings_updated"))),
    **_remap("events.AdmissionStage", *((action, "stage_id") for action in (*_STAGE, *_APPLICATION)),
             ("event.application.stage_advanced", "from_stage_id")),
    **_remap("events.AdmissionStageAssignment", ("event.admission_stage.review_submitted", "assignment_id"),
             ("event.admission_stage.review_recused", "assignment_id")),
    **_remap("events.HackathonApplication", *((action, "application_id") for action in _APPLICATION)),
    **_remap("events.ApplicationDecision", *((action, "decision_id") for action in _APPLICATION)),
    **_remap("events.EventAttendanceRound", ("event.attendance.sent", "round_id")),
    **_remap("events.EventRegistration", ("event.attendance.replied", "registration_id"),
             ("event.crew.place_created", "registration_id"),
             ("event.crew.place_released", "registration_id"), ("event.checkin_list.scanned", "registration_id")),
    **_remap("events.EventCrewMember", *((action, "crew_id") for action in _CREW)),
    **_remap("events.EventCheckInList", *((action, "list_id") for action in _LISTS)),
    **_remap("events.EventAddon", ("event.checkin_list.created", "addon_id")),
}
