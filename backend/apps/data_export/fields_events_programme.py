"""Private programme values omitted from readable exports; portable custody stays scoped."""
from apps.encryption.registry_events_programme import programme_pii_fields


PRIVATE_FIELDS = frozenset((entry[0], entry[1]) for entry in programme_pii_fields(lambda *args: args)) | {
    ("events.HackathonSubmission", "form_answers"),
    ("events.HackathonSubmission", "triage_reason"),
    ("events.SubmissionSnapshot", "project"),
    ("events.SubmissionSnapshot", "sealed_member_ids"),
    ("events.SubmissionSnapshot", "amendment_reason"),
    ("events.SubmissionIntegrityFlag", "evidence"),
    ("events.SubmissionIntegrityFlag", "reason"),
    ("events.SubmissionAsset", "original_filename"),
    ("events.SubmissionAsset", "manifest"),
    ("events.HackathonParticipantAsset", "manifest"),
    ("events.HackathonParticipantAsset", "original_filename"),
    ("events.EventAnswerDerivation", "source_dob_envelope"),
    ("events.EventAnswerDerivation", "source_history"),
}
