"""Ready to install under /api/v1/admin/. No authority from URL issuance."""
from django.urls import path
from .views_projects import AmendView, TriageView
from .views_downloads import AssetDownloadView

from .views_admin_reads import OrganizerProjectListView, OrganizerProjectDetailView
from .views_integrity import SubmissionIntegrityListView, SubmissionIntegrityView
from .views_stages import (SubmissionStagesView, StageShortlistView, StageShortlistPreviewView, StageShortlistApplyView,
                           StageShortlistPublishView, StageExtensionView, StageTriageView)

STAGE = "events/<int:pk>/submission-stages/<int:stage_id>/"

urlpatterns = [
    path("events/<int:pk>/submissions/", OrganizerProjectListView.as_view(), name="events-programme-admin-submissions"),
    path("events/<int:pk>/submissions/<int:submission_id>/", OrganizerProjectDetailView.as_view(), name="events-programme-admin-submission-detail"),
    path("events/<int:pk>/submissions/integrity/", SubmissionIntegrityListView.as_view(), name="events-programme-admin-submissions-integrity-list"),
    path("events/<int:pk>/submissions/<int:submission_id>/integrity/", SubmissionIntegrityView.as_view(), name="events-programme-admin-submissions-integrity"),
    path("events/<int:pk>/submissions/<int:submission_id>/amend/", AmendView.as_view(), name="events-programme-admin-submissions-amend"),
    path("events/<int:pk>/submissions/<int:submission_id>/triage/", TriageView.as_view(), name="events-programme-admin-submissions-triage"),
    path("events/<int:pk>/assets/<int:asset_id>/download/", AssetDownloadView.as_view(staff=True), name="events-programme-admin-assets-download"),
    path("events/<int:pk>/assets/<int:asset_id>/preview/", AssetDownloadView.as_view(staff=True), name="events-programme-admin-assets-preview"),
    # #177-#180: submission stages, shortlist gates, extensions and per-stage triage.
    path("events/<int:pk>/submission-stages/", SubmissionStagesView.as_view(), name="events-programme-admin-submission-stages"),
    path(STAGE + "shortlist/", StageShortlistView.as_view(), name="events-programme-admin-submission-stage-shortlist"),
    path(STAGE + "shortlist/preview/", StageShortlistPreviewView.as_view(), name="events-programme-admin-submission-stage-shortlist-preview"),
    path(STAGE + "shortlist/apply/", StageShortlistApplyView.as_view(), name="events-programme-admin-submission-stage-shortlist-apply"),
    path(STAGE + "shortlist/publish/", StageShortlistPublishView.as_view(), name="events-programme-admin-submission-stage-shortlist-publish"),
    path(STAGE + "extensions/", StageExtensionView.as_view(), name="events-programme-admin-submission-stage-extensions"),
    path(STAGE + "triage/", StageTriageView.as_view(), name="events-programme-admin-submission-stage-triage"),
]
