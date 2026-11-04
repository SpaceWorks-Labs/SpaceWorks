"""Explicit programme model imports; retained independently of runtime gates."""
from apps.events.answer_derivations.models import (
    EventAnswerDerivation,
)
from apps.events.certificates.library_models import (
    EventCertificateLibraryTemplate, EventCertificateLibraryArtwork, EventCertificateLibraryRevision, EventCertificateLibraryCommand,
)
from apps.events.certificates.models import (
    EventCertificatePublicationPolicy, CertificateIssueBatch, CertificateIssueBatchItem,
)
from apps.events.certificates.print_models import (
    EventBadgeTemplateRevision, BadgePrintJob, BadgePrintResource, BadgePrintCleanupReceipt,
)
from apps.events.contributions.models_admission import (
    EventContributorAdmission,
)
from apps.events.contributions.models_notices import (
    EventContributorNotice,
)
from apps.events.contributions.models_policy import (
    EventRoleAnswerRevision, EventRequirementOverride, EventContributorRequirementCompletion,
)
from apps.events.contributions.models_roles import (
    EventRolePosting, EventRoleAssignment, EventGrantEntitlement, EventSponsor, EventSponsorTrack,
)
from apps.events.contributions.models_shifts import (
    EventShift, EventShiftSignup, EventShiftAttendance, EventContributionHours, EventContributionHoursEntry, EventShiftAttendanceCorrection,
)
from apps.events.credentials.models import (
    EventRegistrationCredential, EventCredentialCommand,
)
from apps.events.hackathons.admission_models import (
    HackathonConfig, HackathonCocRevision, HackathonApplicationCohort, HackathonApplication, AdmissionWaitlistSweep, HackathonApplicationAnswerRevision,
)
from apps.events.hackathons.review_models import (
    ApplicationReviewAssignment, ApplicationReview, ApplicationReviewConflict, ApplicationDecisionBatch, ApplicationDecision,
)
from apps.events.hackathons.team_models import (
    HackathonTeam, HackathonTeamMember, HackathonTeamInvite, HackathonFinderProfile, TeamComment, HackathonTeamException,
)
from apps.events.judging.models_consent import (
    ParticipantSponsorResumeConsent, SponsorResumeConsentHistory,
)
from apps.events.judging.models_definitions import (
    HackathonTrack, HackathonPrize, JudgingRound, JudgingCriterion,
)
from apps.events.judging.models_results import (
    EventResultRevision, EventResultRound, EventAward, ResultAnnouncement, ResultPublicationState, SponsorWinnerProposal, JudgingNotice,
)
from apps.events.judging.models_pairwise import (
    JudgePairwiseComparison, JudgePairwiseInvalidation, JudgePairwiseCursor,
)
from apps.events.judging.models_scoring import (
    JudgingReason, JudgeAssignment, JudgingRoundProject, JudgeScore, JudgeRankingBallot, JudgeRankingChoice, JudgeConflict,
)
from apps.events.mentoring.models_operations import (
    MentorAssignmentRun, MentorAttentionPreference,
)
from apps.events.mentoring.models_queue import (
    MentorProfile, MentorTeamAssignment, EventHelpType, EventHelpRequest, EventHelpAction, EventHelpComment, OfficeHoursBooking, OfficeHoursChange,
)
from apps.events.mentoring.models_rounds import (
    MentorRound, MentorRoundLock, MentorRoundCheckin, MentorConflict, MentorNomination, MentorImportPreview, MentorNotificationIntent,
)
from apps.events.models_broadcasts import (
    EventBroadcastPreview,
)
from apps.events.models_commands import (
    EventCommandReceipt,
)
from apps.events.profile_photos.models import (
    EventMemberPresentation, EventMemberCard, EventPresentationCommand,
)
from apps.events.programme.form_models import (
    EventFormRevision,
)
from apps.events.submissions.gallery_models import (
    GalleryConsent, GalleryConsentItem, GalleryConsentRevision, GalleryPublication, GalleryEntry, GalleryEntryAsset, GalleryEntryLink, GalleryAmendment,
)
from apps.events.submissions.models_assets import (
    SubmissionAsset, HackathonParticipantAsset, EventAssetUsage, SubmissionAssetWork,
    EventAssetObligation, EventProgrammeSweepCursor,
)
from apps.events.submissions.models_projects import (
    HackathonSubmission, SubmissionSnapshot, SubmissionLink, SnapshotAsset, SnapshotLink, SnapshotTrack, SnapshotPrize, SubmissionIntegrityFlag,
)

__all__ = [
    'EventContributorRequirementCompletion',
    'BadgePrintCleanupReceipt',
    'EventAssetObligation', 'EventProgrammeSweepCursor',
    'EventBroadcastPreview', 'EventCommandReceipt', 'EventAnswerDerivation', 'EventCertificateLibraryTemplate',
    'EventCertificateLibraryArtwork', 'EventCertificateLibraryRevision', 'EventCertificateLibraryCommand', 'EventCertificatePublicationPolicy',
    'CertificateIssueBatch', 'CertificateIssueBatchItem', 'EventBadgeTemplateRevision', 'BadgePrintJob',
    'BadgePrintResource', 'EventContributorAdmission', 'EventContributorNotice', 'EventRoleAnswerRevision',
    'EventRequirementOverride', 'EventRolePosting', 'EventRoleAssignment', 'EventGrantEntitlement',
    'EventSponsor', 'EventSponsorTrack', 'EventShift', 'EventShiftSignup',
    'EventShiftAttendance', 'EventContributionHours', 'EventContributionHoursEntry', 'EventShiftAttendanceCorrection',
    'EventRegistrationCredential', 'EventCredentialCommand', 'HackathonConfig', 'HackathonCocRevision',
    'HackathonApplicationCohort', 'HackathonApplication', 'AdmissionWaitlistSweep', 'HackathonApplicationAnswerRevision',
    'ApplicationReviewAssignment', 'ApplicationReview', 'ApplicationReviewConflict', 'ApplicationDecisionBatch',
    'ApplicationDecision', 'HackathonTeam', 'HackathonTeamMember', 'HackathonTeamInvite',
    'HackathonFinderProfile', 'TeamComment', 'HackathonTeamException', 'ParticipantSponsorResumeConsent',
    'SponsorResumeConsentHistory', 'HackathonTrack', 'HackathonPrize', 'JudgingRound',
    'JudgingCriterion', 'EventResultRevision', 'EventResultRound', 'EventAward',
    'ResultAnnouncement', 'ResultPublicationState', 'SponsorWinnerProposal', 'JudgingNotice',
    'JudgingReason', 'JudgeAssignment', 'JudgingRoundProject', 'JudgeScore',
    'JudgeRankingBallot', 'JudgeRankingChoice', 'JudgeConflict', 'MentorAssignmentRun',
    'JudgePairwiseComparison', 'JudgePairwiseInvalidation', 'JudgePairwiseCursor',
    'MentorAttentionPreference', 'MentorProfile', 'MentorTeamAssignment', 'EventHelpType',
    'EventHelpRequest', 'EventHelpAction', 'EventHelpComment', 'OfficeHoursBooking',
    'OfficeHoursChange', 'MentorRound', 'MentorRoundLock', 'MentorRoundCheckin',
    'MentorConflict', 'MentorNomination', 'MentorImportPreview', 'MentorNotificationIntent',
    'EventMemberPresentation', 'EventMemberCard', 'EventPresentationCommand', 'EventFormRevision',
    'GalleryConsent', 'GalleryConsentItem', 'GalleryConsentRevision', 'GalleryPublication',
    'GalleryEntry', 'GalleryEntryAsset', 'GalleryEntryLink', 'GalleryAmendment',
    'SubmissionAsset', 'HackathonParticipantAsset', 'EventAssetUsage', 'SubmissionAssetWork',
    'HackathonSubmission', 'SubmissionSnapshot', 'SubmissionLink', 'SnapshotAsset',
    'SnapshotLink', 'SnapshotTrack', 'SnapshotPrize', 'SubmissionIntegrityFlag',
]
