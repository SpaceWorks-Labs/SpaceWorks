"""Literal deployment-global uniqueness decisions, excluding tenant-rooted constraints."""
from .unique_values_policy import FRESH, PRESERVE, REMAP, _policy
from .insertion_errors import ArchiveFormatError
from .unique_value_generators import _refuses_collision


@_refuses_collision
def refuse_identity_collision(row, target, value):
    raise ArchiveFormatError("An opaque programme identity already exists; import refused.")

RULES = {
    ('events.ApplicationDecision', 'ha_one_application_draft'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.ApplicationDecision', 'ha_one_cohort_draft'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.ApplicationReviewAssignment', 'ha_review_application_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.ApplicationReviewAssignment', 'ha_review_cohort_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAnswerDerivation', 'event_derivation_app_question'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAnswerDerivation', 'event_derivation_reg_question'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAnswerDerivation', 'event_derivation_role_question'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAttendanceCertificate', 'event_cert_reg_live_v2'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAttendanceCertificate', 'event_cert_reg_revision_v2'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAttendanceCertificate', 'event_cert_role_live_v2'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventAttendanceCertificate', 'event_cert_role_revision_v2'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventCertificateArtwork', 'field:resource_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='resource_id', generator=refuse_identity_collision),
    ('events.EventCertificateLibraryArtwork', 'field:object_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventCertificateLibraryArtwork', 'field:resource_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='resource_id', generator=refuse_identity_collision),
    ('events.EventContributionHours', 'field:signup'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventContributionHoursEntry', 'event_hours_revision_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventContributorAdmission', 'field:assignment'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventHelpRequest', 'mentor_one_claimed_help'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventMemberCard', 'field:public_id'): _policy(FRESH, "Source public card URLs are replaced under reset target consent."),
    ('events.EventShiftAttendance', 'field:signup'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventShiftSignup', 'event_shift_member_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.EventSponsorTrack', 'event_sponsor_track_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.GalleryConsent', 'field:team'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.GalleryEntry', 'ev_gallery_entry_snapshot'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.GalleryEntry', 'field:public_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='public_id', generator=refuse_identity_collision),
    ('events.GalleryEntryAsset', 'field:public_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='public_id', generator=refuse_identity_collision),
    ('events.HackathonApplication', 'field:registration'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonApplicationCohort', 'field:team'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonParticipantAsset', 'field:object_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonParticipantAsset', 'field:public_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='public_id', generator=refuse_identity_collision),
    ('events.HackathonParticipantAsset', 'field:staging_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonParticipantAsset', 'field:verification_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonSubmission', 'field:team'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.HackathonTeam', 'field:public_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='public_id', generator=refuse_identity_collision),
    ('events.HackathonTeamMember', 'ha_one_live_team_request'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.JudgeAssignment', 'ev_judge_snapshot_once'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.JudgeConflict', 'ev_judge_conflict'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.JudgeRankingBallot', 'ev_ballot_once'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.JudgeRankingChoice', 'ev_ballot_rank'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.JudgeScore', 'field:assignment'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.MentorConflict', 'mentor_conflict_live_kind'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.MentorNomination', 'mentor_nomination_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.MentorProfile', 'field:assignment'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.MentorRoundCheckin', 'mentor_round_team_checkin'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.MentorTeamAssignment', 'mentor_team_live_unique'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.OfficeHoursBooking', 'office_hours_live_team_slot'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.OfficeHoursBooking', 'office_hours_live_drop_in_slot'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.ResultAnnouncement', 'field:result'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.ResultPublicationState', 'field:current_announcement'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.SubmissionAsset', 'field:object_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.SubmissionAsset', 'field:public_id'): _policy(PRESERVE, "Preserve immutable opaque identity; collisions require owner resolution.", field='public_id', generator=refuse_identity_collision),
    ('events.SubmissionAsset', 'field:staging_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
    ('events.SubmissionAsset', 'field:verification_key'): _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."),
}

from .catalog_r2_l7 import UNIQUE_CONSTRAINTS as _L7_UNIQUE  # noqa: E402
RULES.update({key: _policy(REMAP, "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse.") for key in _L7_UNIQUE})
from .catalog_r2_l21b import UNIQUE_CONSTRAINTS as _L21B_UNIQUE  # noqa: E402
RULES.update({key: _policy(REMAP, "Typed owners or OneToOne scopes follow the target allocation; duplicate tuples refuse.") for key in _L21B_UNIQUE})
