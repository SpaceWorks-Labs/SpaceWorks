"""Release-2 lane L21a (applications, review stages, attendance, crew, lists): tenant-dump fields and authority.

Review stages with their panels, assignments, reviews and stage entries, the per-event
switches, attendance rounds and replies, the crew and the check-in lists travel with their
event (data_export `classification_r2_l21a`). A panel seat and a crew place are authority
over one event's review workspace and a free place; they travel only for a full user and
the target's own event authority still decides every later action.
"""

FIELD_NAMES = {
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
    "events.EventCheckInList": "id makerspace event name kind after_entry addon per_person archived_at position "
                               "created_by created_at",
    "events.EventCheckInListScan": "id makerspace checkin_list registration operation_id actor scanned_at undone_at "
                                   "undone_by",
}
FIELD_NAMES = {label: frozenset(names.split()) for label, names in FIELD_NAMES.items()}
EXTRA_FIELDS = {
    "events.EventRegistration": frozenset({"is_crew", "pay_by"}),
    "events.ApplicationDecision": frozenset({"stage"}),
    "event_reimbursements.ReimbursementProgramme": frozenset({"min_application_stage"}),
    "event_reimbursements.GrantRequest": frozenset({"kind"}),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep, holder = disposition.PRESERVE, (disposition.PRESERVE, disposition.DROP)
    return (
        *same("events.AdmissionStage", "state reviews_per_application blind criteria frozen_at version", keep,
              "A stage's settings and freeze are the event's own review history."),
        *same("events.AdmissionStageReviewer", "reviewer removed_at", holder,
              "A panel seat travels with a full user; a stub-linked seat does not. Target authority still decides."),
        *same("events.AdmissionStageAssignment", "reviewer state", keep,
              "Who was asked to review and what they did is historical review evidence."),
        *same("events.AdmissionStageEntry", "kind stage", keep, "Append-only stage history."),
        *same("events.EventParticipationSettings", "stage_advanced_email attendance_free_on_no crew_signup_open "
              "crew_approval_required crew_public_section", keep, "The event's own switches."),
        *same("events.EventAttendanceReply", "answer effect", keep, "A person's own answer and what it changed."),
        *same("events.EventCrewMember", "member state show_publicly", holder,
              "A crew role travels with a full user; a stub-linked role does not."),
        *same("events.EventCheckInList", "after_entry archived_at per_person position", keep, "The list's own rules."),
        *same("events.EventCheckInListScan", "undone_at", keep, "The record that a collection was undone."),
        *same("events.EventRegistration", "pay_by", disposition.RESET,
              "A running pay window is not carried to the target; staff re-open the offer there."),
    )
