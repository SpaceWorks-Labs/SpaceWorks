"""Programme sources stay visible to the authorization-input drift guard."""
from .authority_events_programme_1 import FIELDS as F0
from .authority_events_programme_2 import FIELDS as F1
from .authority_events_programme_3 import FIELDS as F2
from .authority_events_programme_4 import FIELDS as F3

FIELDS = {
    ('events.EventRoleAssignment', 'host_waiver'): 'Exact host waiver consent is source evidence, reset on tenant import; target admission requires its current waiver.',
    ('events.EventRoleAssignment', 'host_waiver_version_accepted'): 'Source waiver version grants no target admission; reset and reaccept current target terms.',
    ('events.EventRoleAssignment', 'host_waiver_accepted_at'): 'Source consent timestamp is not target acceptance; reset on import.',
    **F0,
    **F1,
    **F2,
    **F3,
    # Base-model fields that programme authorization sources read (drift guard).
    ('bookings.BookableSpace', 'capacity'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('bookings.BookableSpace', 'custom_form'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('bookings.BookableSpace', 'image_key'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('bookings.BookableSpace', 'payment_amount'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('bookings.BookableSpace', 'public_token'): 'Public URL identity read by programme resolution; it identifies a page and grants no staff authority.',
    ('events.Event', 'capacity'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.Event', 'custom_form'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.Event', 'image_key'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.Event', 'payment_amount'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.Event', 'public_token'): 'Public URL identity read by programme resolution; it identifies a page and grants no staff authority.',
    ('events.EventSeries', 'capacity'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.EventSeries', 'custom_form'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.EventSeries', 'image_key'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.EventSeries', 'payment_amount'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('events.EventSeries', 'public_token'): 'Public URL identity read by programme resolution; it identifies a page and grants no staff authority.',
    ('events.Event', 'series_override_fields'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('machines.Machine', 'image_key'): 'Ordinary tenant content read by programme preparation (clone, website, admission); it travels as data and grants no target authority.',
    ('makerspaces.Makerspace', 'public_site_enabled'): 'Publication switch read by programme pages; the target applies its own publication policy.',
    ('makerspaces.MakerspaceMembership', 'verified_by'): 'Remapped verification attribution read by programme admission; history alone grants no target authority.',
}
SCANNED_LABELS = frozenset(('events.EventAnswerDerivation', 'events.EventCertificateLibraryTemplate', 'events.EventCertificateLibraryArtwork', 'events.EventCertificateLibraryRevision', 'events.EventCertificatePublicationPolicy', 'events.EventBadgeTemplateRevision', 'events.EventContributorAdmission', 'events.EventRoleAnswerRevision', 'events.EventRequirementOverride', 'events.EventRolePosting', 'events.EventRoleAssignment', 'events.EventSponsor', 'events.EventSponsorTrack', 'events.EventShift', 'events.EventShiftSignup', 'events.EventShiftAttendance', 'events.EventContributionHours', 'events.EventContributionHoursEntry', 'events.EventShiftAttendanceCorrection', 'events.HackathonConfig', 'events.HackathonCocRevision', 'events.HackathonApplicationCohort', 'events.HackathonApplication', 'events.HackathonApplicationAnswerRevision', 'events.ApplicationReviewAssignment', 'events.ApplicationReview', 'events.ApplicationReviewConflict', 'events.ApplicationDecisionBatch', 'events.ApplicationDecision', 'events.HackathonTeam', 'events.HackathonTeamMember', 'events.HackathonFinderProfile', 'events.TeamComment', 'events.HackathonTeamException', 'events.ParticipantSponsorResumeConsent', 'events.SponsorResumeConsentHistory', 'events.HackathonTrack', 'events.HackathonPrize', 'events.JudgingRound', 'events.JudgingCriterion', 'events.EventResultRevision', 'events.EventResultRound', 'events.EventAward', 'events.ResultAnnouncement', 'events.ResultPublicationState', 'events.SponsorWinnerProposal', 'events.JudgingReason', 'events.JudgeAssignment', 'events.JudgingRoundProject', 'events.JudgeScore', 'events.JudgeRankingBallot', 'events.JudgeRankingChoice', 'events.JudgeConflict', 'events.MentorAssignmentRun', 'events.MentorProfile', 'events.MentorTeamAssignment', 'events.EventHelpType', 'events.EventHelpRequest', 'events.EventHelpAction', 'events.EventHelpComment', 'events.OfficeHoursBooking', 'events.OfficeHoursChange', 'events.MentorRound', 'events.MentorRoundCheckin', 'events.MentorConflict', 'events.MentorNomination', 'events.EventMemberPresentation', 'events.EventMemberCard', 'events.EventFormRevision', 'events.GalleryConsent', 'events.GalleryConsentItem', 'events.GalleryConsentRevision', 'events.GalleryPublication', 'events.GalleryEntry', 'events.GalleryEntryAsset', 'events.GalleryEntryLink', 'events.GalleryAmendment', 'events.SubmissionAsset', 'events.HackathonParticipantAsset', 'events.EventAssetUsage', 'events.HackathonSubmission', 'events.SubmissionSnapshot', 'events.SubmissionLink', 'events.SnapshotAsset', 'events.SnapshotLink', 'events.SnapshotTrack', 'events.SnapshotPrize', 'events.SubmissionIntegrityFlag'))
SOURCE_PATHS = (
    'encryption/maintenance_programme.py',
    'events/programme/prepared_forms.py',
    'events/programme/draft_sources.py',
    'events/programme/answer_projection.py',
    'events/certificates/contribution_proof.py',
    'events/certificates/clone_designs.py',
    'events/clone_preparation.py',
    'events/website_preparation.py',
    'events/submissions/requirements.py',
    'events/submissions/notifications.py',
    'events/contracts/admission_registration.py',
    'events/contributions/runtime.py',
    'events/contributions/requirements_adapter.py',
    'events/contributions/grant_sources.py',
    'events/contributions/requirements_workflow.py',
    'events/contributions/team_access.py',
    'events/credentials/preparation.py',
    'events/services_registration_preparation.py',
    'events/services_registration_helpers.py',
    'events/profile_photos/purge_scope.py',
    'events/services_registration_admission.py',
    'events/services_write_boundary.py',
    'events/programme_locks.py',
    'events/contracts/read_registration.py',
    'events/contracts/certificate_registration.py',
    'events/contracts/photo_registration.py',
    'events/judging/provider_runtime.py',
    'events/judging/provider_subjects.py',
    'events/judging/provider_values.py',
    'events/submissions/boundary_runtime.py',
    'events/submissions/project_adapter.py',
    'events/profile_photos/deletion.py',
    'events/profile_photos/erasure.py',
    'events/profile_photos/source_lifecycle.py',
    'events/answer_derivations/subjects.py',
    'events/certificates/print_policy.py',
    'events/certificates/subjects.py',
    'events/contributions/authority.py',
    'events/contributions/certificate_subjects.py',
    'events/contributions/models_policy.py',
    'events/contributions/role_policy.py',
    'events/contributions/role_workflow.py',
    'events/contributions/shift_workflow.py',
    'events/contributions/sources.py',
    'events/contributions/subjects.py',
    'events/credentials/boundary.py',
    'events/hackathons/admission_subjects.py',
    'events/hackathons/admission_transactions.py',
    'events/judging/boundary.py',
    'events/judging/conflicts.py',
    'events/judging/eligibility.py',
    'events/judging/sponsor_consent_workflow.py',
    'events/mentoring/policy.py',
    'events/profile_photos/policy.py',
    'events/submissions/boundary_adapter.py',
    'events/submissions/read_policy.py',
)

from .catalog_r2_l7 import AUTHORITY_FIELDS as _L7_AUTHORITY, FIELD_NAMES as _L7_FIELD_NAMES  # noqa: E402
FIELDS.update(_L7_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_L7_FIELD_NAMES)
from .catalog_r2_l21b import AUTHORITY_FIELDS as _L21B_AUTHORITY, FIELD_NAMES as _L21B_FIELD_NAMES  # noqa: E402
FIELDS.update(_L21B_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_L21B_FIELD_NAMES)
from .catalog_r2_submit_content import AUTHORITY_FIELDS as _SC_AUTHORITY, FIELD_NAMES as _SC_FIELD_NAMES  # noqa: E402
FIELDS.update(_SC_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_SC_FIELD_NAMES)
from .catalog_hackmoney import AUTHORITY_FIELDS as _HM_AUTHORITY, FIELD_NAMES as _HM_FIELD_NAMES  # noqa: E402
FIELDS.update(_HM_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_HM_FIELD_NAMES)
from .catalog_r2_peoples_choice import AUTHORITY_FIELDS as _PC_AUTHORITY, FIELD_NAMES as _PC_FIELD_NAMES  # noqa: E402
FIELDS.update(_PC_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_PC_FIELD_NAMES)
from .catalog_r2_certificates import AUTHORITY_FIELDS as _CERT_AUTHORITY, FIELD_NAMES as _CERT_FIELD_NAMES  # noqa: E402
FIELDS.update(_CERT_AUTHORITY)
SCANNED_LABELS = SCANNED_LABELS | frozenset(_CERT_FIELD_NAMES)
