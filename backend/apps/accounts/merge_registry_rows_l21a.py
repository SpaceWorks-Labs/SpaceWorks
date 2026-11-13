"""Account-merge dispositions for lane L21a (applications, review stages, attendance, crew, lists)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."
_HISTORY = "Append-only attribution of a staff or member decision; stays with the account that acted."
_PERSON = ("One live panel seat or crew place per person and event; it moves to the survivor unless the "
           "survivor already holds one, and the loser stays on the shell.")

ROWS = (
    (K, "events.AdmissionStage", "created_by", _HISTORY),
    (U, "events.AdmissionStageReviewer", "reviewer", _PERSON),
    (K, "events.AdmissionStageReviewer", "added_by", _HISTORY),
    (K, "events.AdmissionStageAssignment", "reviewer", _HISTORY),
    (K, "events.AdmissionStageEntry", "actor", _HISTORY),
    (R, "events.EventParticipationSettings", "updated_by", _MUTABLE),
    (K, "events.EventAttendanceRound", "sent_by", _HISTORY),
    (U, "events.EventCrewMember", "member", _PERSON),
    (K, "events.EventCrewMember", "decided_by", _HISTORY),
    (K, "events.EventCheckInList", "created_by", _HISTORY),
    (K, "events.EventCheckInListScan", "actor", _HISTORY),
    (K, "events.EventCheckInListScan", "undone_by", _HISTORY),
)
