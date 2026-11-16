"""Literal Lane A integration manifest; G owns every registry/migration edit."""

MODEL_IMPORTS = (
    ("apps.events.hackathons.admission_models", "HackathonConfig"),
    ("apps.events.hackathons.admission_models", "HackathonCocRevision"),
    ("apps.events.hackathons.admission_models", "HackathonApplicationCohort"),
    ("apps.events.hackathons.admission_models", "HackathonApplication"),
    ("apps.events.hackathons.admission_models", "AdmissionWaitlistSweep"),
    ("apps.events.hackathons.admission_models", "HackathonApplicationAnswerRevision"),
    ("apps.events.hackathons.review_models", "ApplicationReviewAssignment"),
    ("apps.events.hackathons.review_models", "ApplicationReview"),
    ("apps.events.hackathons.review_models", "ApplicationReviewConflict"),
    ("apps.events.hackathons.review_models", "ApplicationDecisionBatch"),
    ("apps.events.hackathons.review_models", "ApplicationDecision"),
    ("apps.events.hackathons.team_models", "HackathonTeam"),
    ("apps.events.hackathons.team_models", "HackathonTeamMember"),
    ("apps.events.hackathons.team_models", "HackathonTeamInvite"),
    ("apps.events.hackathons.team_models", "HackathonFinderProfile"),
    ("apps.events.hackathons.team_models", "TeamComment"),
    ("apps.events.hackathons.team_models", "HackathonTeamException"),
)

PII_FIELDS = (
    ("events.HackathonApplication", "answers_snapshot", "event.makerspace_id", "source", "none"),
    ("events.HackathonApplication", "profile_snapshot", "event.makerspace_id", "source", "none"),
    ("events.HackathonApplication", "admission_draft", "event.makerspace_id", "source", "none"),
    ("events.HackathonApplicationAnswerRevision", "answers_snapshot", "application.event.makerspace_id", "source", "none"),
    ("events.HackathonApplicationAnswerRevision", "profile_snapshot", "application.event.makerspace_id", "source", "none"),
    ("events.ApplicationReview", "notes", "assignment.event.makerspace_id", "source", "none"),
    ("events.TeamComment", "encrypted_body", "team.event.makerspace_id", "source", "none"),
)

CREDENTIAL_MODELS = ("events.HackathonTeamInvite",)
COORDINATION_MODELS = ("events.AdmissionWaitlistSweep",)
APPEND_ONLY_MODELS = ("events.HackathonCocRevision", "events.HackathonApplicationAnswerRevision", "events.ApplicationReview", "events.TeamComment", "events.HackathonTeamException")
OBJECT_FIELDS = ()

REGISTRATION_TRANSITIONS = ("offer", "waitlist", "reject", "confirm", "cancel", "reopen", "event_cancel")
NOTICE_KINDS = (
    "application_submitted", "application_offered", "application_waitlisted", "application_rejected",
    "application_confirmed", "application_declined", "application_expired", "application_withdrawn",
    "rsvp_extended", "team_eligibility_changed", "event_cancelled",
)
NOTICE_RENDERER = "apps.events.hackathons.admission_notifications.render_notice"

TASK_ENTRY_POINTS = (
    "apps.events.hackathons.admission_maintenance.expire_due",
    "apps.events.hackathons.admission_maintenance.resume_waitlist",
    "apps.events.hackathons.admission_maintenance.freeze_closed_applications",
)

REQUIRED_SQL_GUARDS = (
    "same_event_application_registration_and_owner",
    "same_event_application_cohort_team",
    "same_event_team_member_application_and_owner",
    "deferred_active_leader_membership",
    "same_event_review_and_decision_subject",
    "same_event_config_gallery_and_result",
    "member_account_kind_for_participant_reviewer_team_refs",
    "append_only_coc_answer_revisions_reviews_comments_exceptions_and_sent_decisions",
    "mapped_pii_write_fences_and_bulk_write_refusal",
)
