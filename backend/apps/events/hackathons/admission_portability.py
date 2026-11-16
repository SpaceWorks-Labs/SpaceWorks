"""Literal field/User dispositions for G's §14 registries, not runtime registration.

Every group is explicit. G must compare its installed registry against ORM fields;
these declarations never dynamically whitelist new fields as safe.
"""
FIELD_GROUPS = {
    "HackathonConfig": {
        "identity_refs": "id event gallery_publication results_revision",
        "authored": "version review_mode application_opens_at application_closes_at application_form team_mode team_min team_max team_lock_at team_eligibility review_count blind_review review_rubric review_round review_round_closed rsvp_days offer_capacity submission_opens_at submission_deadline submission_grace_minutes late_policy attendance_required upload_policy upload_policy_version storage_budget_bytes coc_revision optional_mlh_schema first_results_published_at retention_anchor_at",
        "operational_reset": "enabled finder_enabled",
    },
    "HackathonCocRevision": {"evidence": "id event revision body created_at"},
    "HackathonApplicationCohort": {"private_history": "id event team state version sealed_roster_hash sealed_at"},
    "HackathonApplication": {
        "identity_refs": "id event member registration cohort notified_decision",
        "scoped_pii": "answers_snapshot profile_snapshot admission_draft",
        "private_history": "state version form_schema_version form_revision coc_revision coc_accepted_at optional_consents submitted_at offered_at rsvp_due_at response_at rsvp_accepted_at queue_position_at decision_revision answers_changed_at answer_event_date_revision answer_as_of_date answer_locked_at date_review_required",
    },
    "AdmissionWaitlistSweep": {"omit_coordination": "id event last_queue_at last_application_id last_cohort_id version updated_at"},
    "HackathonApplicationAnswerRevision": {
        "scoped_pii": "answers_snapshot profile_snapshot",
        "private_evidence": "id application sequence form_schema_version form_revision coc_revision coc_accepted_at answer_event_date_revision answer_as_of_date locked_at created_at",
    },
    "ApplicationReviewAssignment": {"private_history": "id event application cohort reviewer round state version rubric_revision assigned_at submitted_at recusal_code"},
    "ApplicationReview": {"scoped_pii": "notes", "private_evidence": "id assignment scores submitted_at"},
    "ApplicationReviewConflict": {"private_history": "id event reviewer application cohort reason_code created_at"},
    "ApplicationDecisionBatch": {"private_history": "id event actor state version created_at committed_at"},
    "ApplicationDecision": {"private_history": "id batch application cohort outcome reason_code expected_subject_version sent_revision active_draft review_override_code sent_at"},
    "HackathonTeam": {
        "private_history": "id event public_id name normalized_name leader state version zone table finder_intro skills public_profile_refs roster_hash locked_at eligibility_issue roster_reopened_until created_at",
        "operational_reset": "seeking_members deleted_at deleted_snapshot",
    },
    "HackathonTeamMember": {"private_history": "id event team application member state joined_at left_at creator"},
    "HackathonTeamInvite": {"omit_credential": "id team token_digest email_digest expires_at revoked_at redeemed_at redeemed_by created_by created_at"},
    "HackathonFinderProfile": {"private_history": "id event member version intro skills", "operational_reset": "opted_in"},
    "TeamComment": {"scoped_pii": "encrypted_body", "private_evidence": "id team author created_at"},
    "HackathonTeamException": {"private_evidence": "id team rule member roster_hash reason_code approved_by created_at valid_until"},
}

# (model, User FK, tenant resolver, role, tenant-import handling)
USER_EDGES = (
    ("HackathonApplication", "member", "event.makerspace_id", "owner_member", "remap_member"),
    ("ApplicationReviewAssignment", "reviewer", "event.makerspace_id", "reviewer_member", "remap_member_inert_no_grant"),
    ("ApplicationReviewConflict", "reviewer", "event.makerspace_id", "reviewer_member", "remap_member_inert_no_grant"),
    ("ApplicationDecisionBatch", "actor", "event.makerspace_id", "nullable_actor", "remap_or_null"),
    ("HackathonTeam", "leader", "event.makerspace_id", "owner_member", "remap_member"),
    ("HackathonTeamMember", "member", "event.makerspace_id", "owner_member", "remap_member"),
    ("HackathonTeamMember", "creator", "event.makerspace_id", "attribution", "remap_attribution_stub"),
    ("HackathonTeamInvite", "redeemed_by", "team.event.makerspace_id", "owner_member", "omit_row"),
    ("HackathonTeamInvite", "created_by", "team.event.makerspace_id", "owner_member", "omit_row"),
    ("HackathonFinderProfile", "member", "event.makerspace_id", "owner_member", "remap_member_optout"),
    ("TeamComment", "author", "team.event.makerspace_id", "owner_member", "remap_member"),
    ("HackathonTeamException", "member", "team.event.makerspace_id", "nullable_member", "remap_member"),
    ("HackathonTeamException", "approved_by", "team.event.makerspace_id", "attribution", "remap_attribution_stub"),
)

IMPORT_RESETS = {
    "HackathonConfig": {"enabled": False, "finder_enabled": False, "gallery_publication": None, "results_revision": None},
    "HackathonTeam": {"seeking_members": False, "public_profile_refs": [], "roster_reopened_until": None, "deleted_at": None, "deleted_snapshot": {}},
    "HackathonFinderProfile": {"opted_in": False},
    "ApplicationDecisionBatch": {"draft_state": "cancelled"},
    "ApplicationDecision": {"active_draft": False},
}
# Preserve original consent evidence in the private import archive; never grant
# current MLH/finder/public authority from those historic JSON records. G resets
# optional_consents.*.accepted=False while retaining timestamp/version history.
# Authored windows import closed. No imported row schedules notices/promotion.
# Canonical registration and payment portability remain G's existing contract.

PURGE_PHASES = (
    ("after_D_results_and_E_certificates", "HackathonConfig.gallery_publication", "HackathonConfig.results_revision"),
    ("clear_circular_notified_pointer", "HackathonApplication.notified_decision"),
    ("dependent_children", "ApplicationDecision", "ApplicationDecisionBatch", "ApplicationReview", "ApplicationReviewConflict", "ApplicationReviewAssignment", "HackathonApplicationAnswerRevision", "TeamComment", "HackathonTeamException", "HackathonTeamInvite", "HackathonFinderProfile", "AdmissionWaitlistSweep"),
    ("clear_application_cohort_then_members", "HackathonApplication.cohort", "HackathonTeamMember"),
    ("domain_roots", "HackathonApplicationCohort", "HackathonTeam", "HackathonApplication", "HackathonCocRevision", "HackathonConfig"),
)
# Registration rows are retained/deleted only through G's event-purge graph, after
# protected application references; global User/Organization/vault/key rows survive.
# A owns no storage keys; typed F/P derivation/resume IDs in snapshots must remap
# through their providers. Public profile refs are display-only and reset on import.
