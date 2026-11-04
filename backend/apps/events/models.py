# Established model barrel pattern; split to keep focused model modules below the file ceiling.
from apps.events.models_event import Event
from apps.events.models_collaborators import EventCollaborator
from apps.events.models_registration import EventRegistration
from apps.events.models_attendance import (
    EventCheckInEvent,
    EventAttendanceCorrection,
)
from apps.events.models_station import EventStationBinding
from apps.events.models_feedback import EventFeedbackResponse, EventFeedbackSurvey
from apps.events.models_certificates import EventAttendanceCertificate
from .models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from apps.events.organizer_models import EventOrganizer
from apps.events.audience_models import EventAudienceOrganization
from apps.events.models_series import (
    EventSeries,
    EventSeriesCollaborator,
    EventSeriesOrganizer,
)
from apps.events.models_calendar import MemberCalendarFeed

from .models_staff_grants import EventStaffGrant, EventStaffGrantInvite
from .models_invites import EventInvite
from .models_tickets import EventTicketType
from .models_promos import EventPromoCode
from .models_categories import EventCategory
from .models_broadcasts import EventBroadcast, EventBroadcastDelivery, EventBroadcastPreview
from .models_website import EventPage, EventPageAsset, EventPageSection, EventSession, EventSessionSpeaker
from .speaker_identity_models import EventSpeaker
from .models_website_revisions import (
    EventPageRevision, EventPageRevisionAsset, EventPageRevisionMember,
    EventSessionIdentity, EventSessionAlias,
)

__all__ = [
    "EventPageRevision", "EventPageRevisionAsset", "EventPageRevisionMember",
    "EventSessionIdentity", "EventSessionAlias",
    "EventCertificateArtwork", "EventCertificateTemplateRevision",
    "EventPage", "EventPageAsset", "EventPageSection", "EventSession", "EventSessionSpeaker",
    "EventBroadcast", "EventBroadcastDelivery", "EventSpeaker",
    "EventStaffGrant", "EventStaffGrantInvite",
    "EventInvite", "EventTicketType", "EventPromoCode", "EventCategory",
    "Event",
    "EventAttendanceCertificate",
    "EventAudienceOrganization",
    "EventCheckInEvent",
    "EventStationBinding",
    "EventCollaborator",
    "EventFeedbackResponse",
    "EventFeedbackSurvey",
    "EventOrganizer",
    "EventRegistration",
    "EventSeries",
    "EventSeriesCollaborator",
    "EventSeriesOrganizer",
    "MemberCalendarFeed",
]

from . import models_programme  # noqa: E402,F401 - explicit retained model discovery
from .models_programme import (
    EventBroadcastPreview, EventCommandReceipt, EventAnswerDerivation, EventCertificateLibraryTemplate,
    EventCertificateLibraryArtwork, EventCertificateLibraryRevision, EventCertificateLibraryCommand, EventCertificatePublicationPolicy,
    CertificateIssueBatch, CertificateIssueBatchItem, EventBadgeTemplateRevision, BadgePrintJob,
    BadgePrintResource, EventContributorAdmission, EventContributorNotice, EventRoleAnswerRevision,
    EventRequirementOverride, EventRolePosting, EventRoleAssignment, EventGrantEntitlement,
    EventSponsor, EventSponsorTrack, EventShift, EventShiftSignup,
    EventShiftAttendance, EventContributionHours, EventContributionHoursEntry, EventShiftAttendanceCorrection,
    EventRegistrationCredential, EventCredentialCommand, HackathonConfig, HackathonCocRevision,
    HackathonApplicationCohort, HackathonApplication, AdmissionWaitlistSweep, HackathonApplicationAnswerRevision,
    ApplicationReviewAssignment, ApplicationReview, ApplicationReviewConflict, ApplicationDecisionBatch,
    ApplicationDecision, HackathonTeam, HackathonTeamMember, HackathonTeamInvite,
    HackathonFinderProfile, TeamComment, HackathonTeamException, ParticipantSponsorResumeConsent,
    SponsorResumeConsentHistory, HackathonTrack, HackathonPrize, JudgingRound,
    JudgingCriterion, EventResultRevision, EventResultRound, EventAward,
    ResultAnnouncement, ResultPublicationState, SponsorWinnerProposal, JudgingNotice,
    JudgingReason, JudgeAssignment, JudgingRoundProject, JudgeScore,
    JudgeRankingBallot, JudgeRankingChoice, JudgeConflict, MentorAssignmentRun,
    JudgePairwiseComparison, JudgePairwiseInvalidation, JudgePairwiseCursor,
    MentorAttentionPreference, MentorProfile, MentorTeamAssignment, EventHelpType,
    EventHelpRequest, EventHelpAction, EventHelpComment, OfficeHoursBooking,
    OfficeHoursChange, MentorRound, MentorRoundLock, MentorRoundCheckin,
    MentorConflict, MentorNomination, MentorImportPreview, MentorNotificationIntent,
    EventMemberPresentation, EventMemberCard, EventPresentationCommand, EventFormRevision,
    GalleryConsent, GalleryConsentItem, GalleryConsentRevision, GalleryPublication,
    GalleryEntry, GalleryEntryAsset, GalleryEntryLink, GalleryAmendment,
    SubmissionAsset, HackathonParticipantAsset, EventAssetUsage, SubmissionAssetWork,
    EventAssetObligation, EventProgrammeSweepCursor,
    BadgePrintCleanupReceipt, EventContributorRequirementCompletion,
    HackathonSubmission, SubmissionSnapshot, SubmissionLink, SnapshotAsset,
    SnapshotLink, SnapshotTrack, SnapshotPrize, SubmissionIntegrityFlag,
)
__all__ += models_programme.__all__

from .staged_forms.models import (
    EventStageForm, EventStageMilestone, StageFormAssignment, StageFormResponse,
    StageFormResponseRevision, StageFormAsset, StageFileCleanup, StageActivationJob, StageReconcileCursor,
)
__all__ += [
    "EventAttendanceCorrection", "EventStageForm", "EventStageMilestone", "StageFormAssignment",
    "StageFormResponse", "StageFormResponseRevision", "StageFormAsset", "StageFileCleanup",
    "StageActivationJob", "StageReconcileCursor",
]

# Release 2 L1: short links, their PII-free visit counter and the event embed allow-list.
from .models_short_links import EventShortLink, EventShortLinkVisitDay  # noqa: E402
from .models_embed_policy import EventEmbedPolicy  # noqa: E402
__all__ += ["EventShortLink", "EventShortLinkVisitDay", "EventEmbedPolicy"]

# Release 2 L2: integrity-check job state, storage cleanup receipts, mentor chat routes.
from .models_r2_l2 import (  # noqa: E402
    MentorAlertRoute, SubmissionIntegrityCheck, SubmissionStorageCleanupReceipt,
)
__all__ += ["MentorAlertRoute", "SubmissionIntegrityCheck", "SubmissionStorageCleanupReceipt"]
