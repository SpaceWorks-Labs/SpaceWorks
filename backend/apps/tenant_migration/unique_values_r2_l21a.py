"""Deployment-global uniqueness for lane L21a's rows (review stages, attendance, crew, lists).

Every rule is scoped to a remapped parent (an event, registration or list), so each follows
its imported parent. Nothing here is a bearer value. The review-stage constraints include
their tenant-owned parent column and carry no deployment-global risk.
"""

from .unique_values_policy import REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."

RULES = {
    ("events.EventParticipationSettings", "field:event"): _policy(REMAP, _FOLLOW),
    ("events.EventAttendanceReply", "field:registration"): _policy(REMAP, _FOLLOW),
    ("events.EventCrewMember", "event_crew_one_live"): _policy(REMAP, _FOLLOW),
    ("events.EventCrewMember", "field:registration"): _policy(REMAP, _FOLLOW),
    ("events.EventCheckInListScan", "event_checkin_list_scan_operation"): _policy(REMAP, _FOLLOW),
}
