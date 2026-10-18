"""Programme sources stay visible to the authorization-input drift guard."""
from .authority_events_programme_1 import FIELDS as F0
from .authority_events_programme_2 import FIELDS as F1
from .authority_events_programme_3 import FIELDS as F2
from .authority_events_programme_4 import FIELDS as F3

FIELDS = {
    **F0,
    **F1,
    **F2,
    **F3,
}
SCANNED_LABELS = frozenset(('events.EventAnswerDerivation', 'events.EventCertificateLibraryTemplate', 'events.EventCertificateLibraryArtwork', 'events.EventCertificateLibraryRevision', 'events.EventCertificatePublicationPolicy', 'events.CertificateIssueBatch', 'events.CertificateIssueBatchItem', 'events.EventBadgeTemplateRevision', 'events.EventContributorAdmission', 'events.EventRoleAnswerRevision', 'events.EventRequirementOverride', 'events.EventRolePosting', 'events.EventRoleAssignment', 'events.EventSponsor', 'events.EventSponsorTrack', 'events.EventShift', 'events.EventShiftSignup', 'events.EventShiftAttendance', 'events.EventContributionHours', 'events.EventContributionHoursEntry', 'events.EventShiftAttendanceCorrection', 'events.HackathonConfig', 'events.HackathonCocRevision', 'events.HackathonApplicationCohort', 'events.HackathonApplication', 'events.HackathonApplicationAnswerRevision', 'events.ApplicationReviewAssignment', 'events.ApplicationReview', 'events.ApplicationReviewConflict', 'events.ApplicationDecisionBatch', 'events.ApplicationDecision', 'events.HackathonTeam', 'events.HackathonTeamMember', 'events.HackathonFinderProfile', 'events.TeamComment', 'events.HackathonTeamException', 'events.ParticipantSponsorResumeConsent', 'events.SponsorResumeConsentHistory', 'events.HackathonTrack', 'events.HackathonPrize', 'events.JudgingRound', 'events.JudgingCriterion', 'events.EventResultRevision', 'events.EventResultRound', 'events.EventAward', 'events.ResultAnnouncement', 'events.ResultPublicationState', 'events.SponsorWinnerProposal', 'events.JudgingReason', 'events.JudgeAssignment', 'events.JudgingRoundProject', 'events.JudgeScore', 'events.JudgeRankingBallot', 'events.JudgeRankingChoice', 'events.JudgeConflict', 'events.MentorAssignmentRun', 'events.MentorProfile', 'events.MentorTeamAssignment', 'events.EventHelpType', 'events.EventHelpRequest', 'events.EventHelpAction', 'events.EventHelpComment', 'events.OfficeHoursBooking', 'events.OfficeHoursChange', 'events.MentorRound', 'events.MentorRoundCheckin', 'events.MentorConflict', 'events.MentorNomination', 'events.EventMemberPresentation', 'events.EventMemberCard', 'events.EventFormRevision', 'events.GalleryConsent', 'events.GalleryConsentItem', 'events.GalleryConsentRevision', 'events.GalleryPublication', 'events.GalleryEntry', 'events.GalleryEntryAsset', 'events.GalleryEntryLink', 'events.GalleryAmendment', 'events.SubmissionAsset', 'events.HackathonParticipantAsset', 'events.EventAssetUsage', 'events.HackathonSubmission', 'events.SubmissionSnapshot', 'events.SubmissionLink', 'events.SnapshotAsset', 'events.SnapshotLink', 'events.SnapshotTrack', 'events.SnapshotPrize', 'events.SubmissionIntegrityFlag'))
SOURCE_PATHS = (
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
