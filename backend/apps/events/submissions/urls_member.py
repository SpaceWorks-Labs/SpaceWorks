"""Ready to install under /api/v1/member/. G owns mounting and route policies."""
from django.urls import path
from .views_projects import ProjectView, ProjectCommandView
from .views_uploads import (UploadView, AssetDetailView, AssetCommandView,
                           ResumeCollectionView, ResumeDetailView, FromSavedView, AssetPartsView, AssetResumeView)
from .views_downloads import AssetDownloadView
from .views_fees import EntryFeeView, ProgrammeChargesView

ROOT = "makerspaces/<int:makerspace_id>/events/<int:pk>/"
TEAM = ROOT + "teams/<int:team_id>/"
urlpatterns = [
    path(TEAM + "submission/", ProjectView.as_view(), name="events-programme-member-teams-submission"),
    path(TEAM + "submission/submit/", ProjectCommandView.as_view(), name="events-programme-member-teams-submission-submit"),
    path(TEAM + "submission/withdraw/", ProjectCommandView.as_view(action="withdraw"), name="events-programme-member-teams-submission-withdraw"),
    # Release 2 L21b: the entry fee and the leader-paid team charge.
    path(TEAM + "charges/", ProgrammeChargesView.as_view(), name="events-programme-member-teams-charges"),
    path(TEAM + "charges/entry-fee/", EntryFeeView.as_view(), name="events-programme-member-teams-entry-fee"),
    path(TEAM + "assets/", UploadView.as_view(), name="events-programme-member-teams-assets-list"),
    path(TEAM + "assets/<int:asset_id>/", AssetDetailView.as_view(), name="events-programme-member-teams-assets-detail"),
    path(TEAM + "assets/<int:asset_id>/parts/", AssetPartsView.as_view(), name="events-programme-member-teams-assets-parts"),
    path(TEAM + "assets/<int:asset_id>/resume/", AssetResumeView.as_view(), name="events-programme-member-teams-assets-resume"),
    path(TEAM + "assets/<int:asset_id>/complete/", AssetCommandView.as_view(), name="events-programme-member-teams-assets-complete"),
    path(TEAM + "assets/<int:asset_id>/abort/", AssetCommandView.as_view(action="abort"), name="events-programme-member-teams-assets-abort"),
    path(ROOT + "assets/<int:asset_id>/download/", AssetDownloadView.as_view(), name="events-programme-member-assets-download"),
    path(ROOT + "assets/<int:asset_id>/preview/", AssetDownloadView.as_view(), name="events-programme-member-assets-preview"),
    path(ROOT + "participant-resumes/", ResumeCollectionView.as_view(), name="events-programme-member-participant-resumes"),
    path(ROOT + "participant-resumes/from-saved/", FromSavedView.as_view(), name="events-programme-member-participant-resume-from-saved"),
    path(ROOT + "participant-resumes/<int:asset_id>/", ResumeDetailView.as_view(), name="events-programme-member-participant-resume-detail"),
    path(ROOT + "participant-resumes/<int:asset_id>/complete/", AssetCommandView.as_view(participant=True), name="events-programme-member-participant-resume-complete"),
    path(ROOT + "participant-resumes/<int:asset_id>/abort/", AssetCommandView.as_view(participant=True, action="abort"), name="events-programme-member-participant-resume-abort"),
    path(ROOT + "participant-resumes/<int:asset_id>/download/", AssetDownloadView.as_view(participant=True), name="events-programme-member-participant-resume-download"),
]
