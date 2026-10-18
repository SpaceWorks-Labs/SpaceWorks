"""Ready to install under /api/v1/admin/. No authority from URL issuance."""
from django.urls import path
from .views_projects import AmendView, TriageView
from .views_downloads import AssetDownloadView

from .views_admin_reads import OrganizerProjectListView, OrganizerProjectDetailView

urlpatterns = [
    path("events/<int:pk>/submissions/", OrganizerProjectListView.as_view(), name="events-programme-admin-submissions"),
    path("events/<int:pk>/submissions/<int:submission_id>/", OrganizerProjectDetailView.as_view(), name="events-programme-admin-submission-detail"),
    path("events/<int:pk>/submissions/<int:submission_id>/amend/", AmendView.as_view(), name="events-programme-admin-submissions-amend"),
    path("events/<int:pk>/submissions/<int:submission_id>/triage/", TriageView.as_view(), name="events-programme-admin-submissions-triage"),
    path("events/<int:pk>/assets/<int:asset_id>/download/", AssetDownloadView.as_view(staff=True), name="events-programme-admin-assets-download"),
    path("events/<int:pk>/assets/<int:asset_id>/preview/", AssetDownloadView.as_view(staff=True), name="events-programme-admin-assets-preview"),
]
