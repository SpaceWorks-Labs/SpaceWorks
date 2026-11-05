"""Release-2 lane L21a (applications, review stages, attendance, crew, check-in lists): literal classification.

Exported with the space: review stages with their panels, assignments, reviews and the
append-only stage entries; the per-event participation switches; attendance rounds and
replies; the event crew; check-in lists and their scans. Stage review notes, attendance
notes and crew answers and dietary needs are scoped PII (encrypted at rest,
`encryption/registry_r2_l21a`). New columns: the crew flag on a registration, the stage an
application decision advances from, the reimbursement stage threshold and request kind.
Nothing here is bearer material: a plan fingerprint and seed authenticate nothing.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "events.AdmissionStage": "id event position name state reviews_per_application blind criteria guidance opens_at "
                             "closes_at assignment_strategy assignment_seed assignment_fingerprint assigned_at "
                             "frozen_at version created_by created_at",
    "events.AdmissionStageReviewer": "id stage reviewer added_by added_at removed_at",
    "events.AdmissionStageAssignment": "id stage application reviewer state plan_fingerprint assigned_at submitted_at",
    "events.AdmissionStageReview": "id assignment scores notes submitted_at",
    "events.AdmissionStageEntry": "id event application stage kind decision reason_code actor created_at",
    "events.EventParticipationSettings": "id makerspace event stage_advanced_email attendance_free_on_no "
                                         "crew_signup_open crew_approval_required crew_public_section updated_by "
                                         "updated_at",
    "events.EventAttendanceRound": "id makerspace event kind state recipients sent sent_by created_at finished_at",
    "events.EventAttendanceReply": "id makerspace event registration asked_at answer note replied_at effect "
                                   "reminded_at",
    "events.EventCrewMember": "id makerspace event member origin crew_role state answers dietary show_publicly "
                              "registration decided_by decided_at version created_at",
    "events.EventCheckInList": "id makerspace event name kind after_entry addon per_person archived_at created_by "
                               "created_at",
    "events.EventCheckInListScan": "id makerspace checkin_list registration operation_id actor scanned_at",
}
FIELD_ADDITIONS = {
    "events.EventRegistration": "is_crew",
    "events.ApplicationDecision": "stage",
    "event_reimbursements.ReimbursementProgramme": "min_application_stage",
    "event_reimbursements.GrantRequest": "kind",
}
NON_CREDENTIAL = {
    ("events.AdmissionStage", "assignment_seed"): "The stored seed that reproduces a reviewer assignment plan.",
    ("events.AdmissionStage", "assignment_fingerprint"): "Digest of the applied assignment plan; authenticates nothing.",
    ("events.AdmissionStage", "state"): "Workflow state, not a bearer credential.",
    ("events.AdmissionStageAssignment", "plan_fingerprint"): "Digest of the plan that created the row.",
    ("events.AdmissionStageAssignment", "state"): "Workflow state, not a bearer credential.",
    ("events.EventAttendanceRound", "state"): "Delivery state, not a bearer credential.",
    ("events.EventCrewMember", "state"): "Workflow state, not a bearer credential.",
    ("events.EventCheckInListScan", "operation_id"): "Idempotency key of one desk scan; authenticates nothing.",
}
_EVENT = P(("event__makerspace",))
DATASET_SPECS = {
    "events.AdmissionStage": ("events/admission_stages.csv", _EVENT),
    "events.AdmissionStageReviewer": ("events/admission_stage_panels.csv", P(("stage__event__makerspace",))),
    "events.AdmissionStageAssignment": ("events/admission_stage_assignments.csv", P(("stage__event__makerspace",))),
    "events.AdmissionStageReview": ("events/admission_stage_reviews.csv",
                                    P(("assignment__stage__event__makerspace",))),
    "events.AdmissionStageEntry": ("events/admission_stage_entries.csv", _EVENT),
    "events.EventParticipationSettings": ("events/participation_settings.csv", P(("makerspace",))),
    "events.EventAttendanceRound": ("events/attendance_rounds.csv", P(("makerspace",))),
    "events.EventAttendanceReply": ("events/attendance_replies.csv", P(("makerspace",))),
    "events.EventCrewMember": ("events/crew.csv", P(("makerspace",))),
    "events.EventCheckInList": ("events/checkin_lists.csv", P(("makerspace",))),
    "events.EventCheckInListScan": ("events/checkin_list_scans.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("events.AdmissionStage", "created_by"),
    ("events.AdmissionStageReviewer", "reviewer"),
    ("events.AdmissionStageReviewer", "added_by"),
    ("events.AdmissionStageAssignment", "reviewer"),
    ("events.AdmissionStageEntry", "actor"),
    ("events.EventParticipationSettings", "updated_by"),
    ("events.EventAttendanceRound", "sent_by"),
    ("events.EventCrewMember", "member"),
    ("events.EventCrewMember", "decided_by"),
    ("events.EventCheckInList", "created_by"),
    ("events.EventCheckInListScan", "actor"),
})
# Stage criteria (keys and labels) and review scores keyed by those criteria: no row ids inside.
JSON_FIELDS = frozenset({("events.AdmissionStage", "criteria"), ("events.AdmissionStageReview", "scores")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
