"""Ready-to-install D URL list. G mounts once under /api/v1/ after policy registration."""

from django.urls import path

from apps.events.submissions import gallery_views as gallery
from . import views_definitions as definitions
from . import views_results as results
from . import views_scoring as scoring
from . import views_sponsors as sponsors
from .views_signals import ShortlistSignals
from .views_sponsor_discovery import AssignedSponsorListView

ADMIN = "admin/events/<int:pk>/"
MEMBER = "member/makerspaces/<int:makerspace_id>/events/<int:pk>/"
PUBLIC = "public/event-programmes/<uuid:public_token>/"


def route(prefix, suffix, view, name):
    return path(prefix + suffix, view.as_view(), name="events-programme-" + name)


urlpatterns = [
    route(ADMIN, "assigned-sponsors/", AssignedSponsorListView, "admin-assigned-sponsors"),
    route(ADMIN, "judging-signals/", ShortlistSignals, "admin-judging-signals"),
    route(ADMIN, "tracks/", definitions.TrackList, "admin-tracks-list"),
    route(ADMIN, "tracks/<int:track_id>/", definitions.TrackDetail, "admin-tracks-detail"),
    route(ADMIN, "prizes/", definitions.PrizeList, "admin-prizes-list"),
    route(ADMIN, "prizes/<int:prize_id>/", definitions.PrizeDetail, "admin-prizes-detail"),
    route(ADMIN, "judging-rounds/", definitions.RoundList, "admin-judging-rounds-list"),
    route(ADMIN, "judging-rounds/<int:round_id>/", definitions.RoundDetail, "admin-judging-rounds-detail"),
    route(ADMIN, "judging-rounds/<int:round_id>/open/", definitions.RoundOpen, "admin-judging-rounds-open"),
    route(ADMIN, "judging-rounds/<int:round_id>/assign/", definitions.RoundAssign, "admin-judging-rounds-assign"),
    route(ADMIN, "judging-rounds/<int:round_id>/close/", definitions.RoundClose, "admin-judging-rounds-close"),
    route(ADMIN, "judging-rounds/<int:round_id>/finalize/", definitions.RoundFinalize, "admin-judging-rounds-finalize"),
    route(ADMIN, "judge-assignments/", scoring.AssignmentList, "admin-judge-assignments-list"),
    route(ADMIN, "judge-assignments/<int:assignment_id>/", scoring.AssignmentDetail, "admin-judge-assignments-detail"),
    route(ADMIN, "judge-assignments/<int:assignment_id>/score/", scoring.AssignmentScore, "admin-judge-assignments-score"),
    route(ADMIN, "judge-assignments/<int:assignment_id>/rank/", scoring.AssignmentRank, "admin-judge-assignments-rank"),
    route(ADMIN, "judge-assignments/<int:assignment_id>/recuse/", scoring.AssignmentRecuse, "admin-judge-assignments-recuse"),
    route(ADMIN, "judge-assignments/<int:assignment_id>/skip/", scoring.AssignmentSkip, "admin-judge-assignments-skip"),
    route(ADMIN, "sponsors/<int:sponsor_id>/submissions/", sponsors.SponsorSubmissions, "admin-sponsors-submissions"),
    route(ADMIN, "sponsors/<int:sponsor_id>/prizes/<int:prize_id>/propose/", sponsors.SponsorWinnerProposal,
          "admin-sponsors-prizes-propose"),
    route(ADMIN, "sponsors/<int:sponsor_id>/resumes/<int:participant_asset_id>/", sponsors.SponsorResumeDownload,
          "admin-sponsor-resume-download"),
    route(ADMIN, "results/preview/", results.ResultsPreview, "admin-results-preview"),
    route(ADMIN, "results/finalize/", results.ResultsFinalize, "admin-results-finalize"),
    route(ADMIN, "results/publish/", results.ResultsPublish, "admin-results-publish"),
    route(ADMIN, "results/correct/", results.ResultsCorrect, "admin-results-correct"),
    route(ADMIN, "gallery/publish/", gallery.GalleryPublish, "admin-gallery-publish"),
    route(ADMIN, "gallery/", gallery.AdminGallery, "admin-gallery-list"),
    route(ADMIN, "gallery/entries/<int:entry_id>/hide/", gallery.GalleryHide, "admin-gallery-entries-hide"),
    route(ADMIN, "gallery/amend/", gallery.GalleryAmend, "admin-gallery-amend"),
    route(ADMIN, "gallery/correct-result/", gallery.GalleryCorrectResult, "admin-gallery-correct-result"),
    route(MEMBER, "resume-consents/", sponsors.ResumeConsents, "member-resume-consents"),
    route(MEMBER, "resume-consents/<int:consent_id>/revoke/", sponsors.ResumeConsentRevoke, "member-resume-consent-revoke"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/", gallery.GalleryConsentDetail, "member-gallery-consent-detail"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/grant/", gallery.GalleryConsentGrant, "member-gallery-consent-grant"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/withdraw/", gallery.GalleryConsentWithdraw, "member-gallery-consent-withdraw"),
    route(PUBLIC, "gallery/", gallery.GalleryList, "public-gallery-list"),
    route(PUBLIC, "gallery/<uuid:entry_public_id>/", gallery.GalleryDetail, "public-gallery-detail"),
    route(PUBLIC, "results/", gallery.PublicResults, "public-results"),
]
