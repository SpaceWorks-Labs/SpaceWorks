"""Ready-to-install D URL list. G mounts once under /api/v1/ after policy registration."""

from django.urls import path

from apps.events.submissions import gallery_views as gallery
from . import views_definitions as definitions
from . import views_pairwise as pairwise
from . import views_results as results
from . import views_scoring as scoring
from . import views_sponsors as sponsors
from . import views_l21b as l21b
from . import views_money as money
from . import views_prize as prize
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
    route(ADMIN, "pairwise-rounds/", pairwise.PairwiseRounds, "admin-pairwise-rounds-list"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/", pairwise.PairwiseState, "admin-pairwise-state"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/next/", pairwise.PairwiseNext, "admin-pairwise-next"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/compare/", pairwise.PairwiseCompare, "admin-pairwise-compare"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/skip/", pairwise.PairwiseSkip, "admin-pairwise-skip"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/recuse/", pairwise.PairwiseRecuse, "admin-pairwise-recuse"),
    route(ADMIN, "judging-rounds/<int:round_id>/pairwise/standings/", pairwise.PairwiseStandings, "admin-pairwise-standings"),
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
    # Release 2 L21b: finalists, progress, score-next, programme options and prize payouts.
    route(ADMIN, "finalists/", l21b.FinalistList, "admin-finalists-list"),
    route(ADMIN, "finalists/preview/", l21b.FinalistPreview, "admin-finalists-preview"),
    route(ADMIN, "finalists/apply/", l21b.FinalistApply, "admin-finalists-apply"),
    route(ADMIN, "finalists/publish/", l21b.FinalistPublish, "admin-finalists-publish"),
    route(ADMIN, "judging-rounds/<int:round_id>/progress/", l21b.RoundProgress, "admin-judging-rounds-progress"),
    route(ADMIN, "judging-rounds/<int:round_id>/next-project/", l21b.NextProject, "admin-judging-rounds-next-project"),
    route(ADMIN, "programme-options/", l21b.ProgrammeOptions, "admin-programme-options"),
    route(ADMIN, "results/send-email/", l21b.ResultsSendEmail, "admin-results-send-email"),
    route(ADMIN, "prize-payouts/", l21b.PrizePayouts, "admin-prize-payouts"),
    route(ADMIN, "prize-payouts/<int:payout_id>/reverse/", l21b.PrizePayoutReverse, "admin-prize-payouts-reverse"),
    # Hack-money (#180): team-charge retry (G15).
    route(ADMIN, "team-charges/missing/", money.MissingTeamCharges, "admin-team-charges-missing"),
    route(ADMIN, "team-charges/<int:team_id>/raise/", money.TeamChargeRaise, "admin-team-charges-raise"),
    # Hack-money (#180 G3-G6/G8/G16, #181 G7): prize splits, claims, outcomes and the prize pool.
    route(ADMIN, "prize-awards/<int:award_id>/split/", prize.AdminPrizeSplit, "admin-prize-split"),
    route(ADMIN, "prize-awards/<int:award_id>/fulfil/", prize.PrizeFulfil, "admin-prize-fulfil"),
    route(ADMIN, "prize-awards/<int:award_id>/forfeit/", prize.PrizeForfeit, "admin-prize-forfeit"),
    route(ADMIN, "prize-outcomes/", prize.PrizeOutcomes, "admin-prize-outcomes"),
    route(ADMIN, "prize-outcomes/<int:outcome_id>/resolve/", prize.PrizeRecoveryResolve, "admin-prize-recovery-resolve"),
    route(ADMIN, "prize-claims/", prize.PrizeClaims, "admin-prize-claims"),
    route(ADMIN, "prize-shares/<int:share_id>/verify/", prize.PrizeClaimVerify, "admin-prize-claim-verify"),
    route(ADMIN, "prize-shares/<int:share_id>/reveal/", prize.PrizeClaimReveal, "admin-prize-claim-reveal"),
    route(ADMIN, "prize-pool/", prize.PrizePool, "admin-prize-pool"),
    route(MEMBER, "prize-awards/<int:award_id>/split/", prize.MemberPrizeSplit, "member-prize-split"),
    route(MEMBER, "prize-shares/<int:share_id>/confirm/", prize.MemberShareConfirm, "member-prize-share-confirm"),
    route(MEMBER, "prize-shares/<int:share_id>/decline/", prize.MemberShareDecline, "member-prize-share-decline"),
    route(MEMBER, "prize-awards/<int:award_id>/claim/", prize.MemberPrizeClaim, "member-prize-claim"),
    route(MEMBER, "prize-awards/<int:award_id>/claim/remove/", prize.MemberPrizeClaimRemove, "member-prize-claim-remove"),
    route("member/makerspaces/<int:makerspace_id>/", "prizes/", prize.MyPrizes, "member-my-prizes"),
    route(PUBLIC, "prizes/", prize.PublicPrizes, "public-prizes"),
    route(MEMBER, "resume-consents/", sponsors.ResumeConsents, "member-resume-consents"),
    route(MEMBER, "resume-consents/<int:consent_id>/revoke/", sponsors.ResumeConsentRevoke, "member-resume-consent-revoke"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/", gallery.GalleryConsentDetail, "member-gallery-consent-detail"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/grant/", gallery.GalleryConsentGrant, "member-gallery-consent-grant"),
    route(MEMBER, "teams/<int:team_id>/gallery-consent/withdraw/", gallery.GalleryConsentWithdraw, "member-gallery-consent-withdraw"),
    route(PUBLIC, "gallery/", gallery.GalleryList, "public-gallery-list"),
    route(PUBLIC, "gallery/<uuid:entry_public_id>/", gallery.GalleryDetail, "public-gallery-detail"),
    route(PUBLIC, "results/", gallery.PublicResults, "public-results"),
]
