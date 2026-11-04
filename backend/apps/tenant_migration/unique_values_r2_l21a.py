"""Deployment-global uniqueness for lane L21a's rows (review stages, attendance, crew, lists).

Every rule is scoped to a remapped parent (an event, stage, assignment, registration or
list), so each follows its imported parent. Nothing here is a bearer value.
"""

from .unique_values_policy import REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."

RULES = {
    ("events.AdmissionStage", "admission_stage_position_unique"): _policy(REMAP, _FOLLOW),
    ("events.AdmissionStageReviewer", "admission_stage_reviewer_live"): _policy(REMAP, _FOLLOW),
    ("events.AdmissionStageAssignment", "admission_stage_assignment_unique"): _policy(REMAP, _FOLLOW),
    ("events.AdmissionStageReview", "field:assignment"): _policy(REMAP, _FOLLOW),
    ("events.EventParticipationSettings", "field:event"): _policy(REMAP, _FOLLOW),
    ("events.EventAttendanceReply", "field:registration"): _policy(REMAP, _FOLLOW),
    ("events.EventCrewMember", "event_crew_one_live"): _policy(REMAP, _FOLLOW),
    ("events.EventCrewMember", "field:registration"): _policy(REMAP, _FOLLOW),
    ("events.EventCheckInListScan", "event_checkin_list_scan_operation"): _policy(REMAP, _FOLLOW),
}
