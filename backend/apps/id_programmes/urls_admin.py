"""Staff ID-programme routes under /api/v1/admin/ (mounted only while the app ships)."""
from django.urls import path

from apps.card_designs.views_staff_photo import ProgrammeCardStaffPhotoView

from .views import (OrganizationProgrammeListView, ProgrammeApprovalView, ProgrammeDesignView,
                    ProgrammeDetailView)
from .views_cards import (ProgrammeCardDetailView, ProgrammeCardDownloadView, ProgrammeCardEmailView,
                          ProgrammeCardJobView, ProgrammeCardListView, ProgrammeCardPhotoRequestView,
                          ProgrammeDecisionView, ProgrammeImportPreviewView, ProgrammeImportView)

_PROGRAMME = "id-programmes/<int:pk>"
_CARD = "id-programme-cards/<int:pk>"

urlpatterns = [
    path("organizations/<int:organization_id>/id-programmes", OrganizationProgrammeListView.as_view(),
         name="admin-organization-id-programmes"),
    path(_PROGRAMME, ProgrammeDetailView.as_view(), name="admin-id-programme"),
    path(f"{_PROGRAMME}/design", ProgrammeDesignView.as_view(), name="admin-id-programme-design"),
    path(f"{_PROGRAMME}/approval", ProgrammeApprovalView.as_view(), name="admin-id-programme-approval"),
    path(f"{_PROGRAMME}/cards", ProgrammeCardListView.as_view(), name="admin-id-programme-cards"),
    path(f"{_PROGRAMME}/cards/decide", ProgrammeDecisionView.as_view(), name="admin-id-programme-decide"),
    path(f"{_PROGRAMME}/imports/preview", ProgrammeImportPreviewView.as_view(),
         name="admin-id-programme-import-preview"),
    path(f"{_PROGRAMME}/imports", ProgrammeImportView.as_view(), name="admin-id-programme-import"),
    path(f"{_PROGRAMME}/card-jobs", ProgrammeCardJobView.as_view(), name="admin-id-programme-card-jobs"),
    path(_CARD, ProgrammeCardDetailView.as_view(), name="admin-id-programme-card"),
    path(f"{_CARD}/download", ProgrammeCardDownloadView.as_view(), name="admin-id-programme-card-download"),
    path(f"{_CARD}/email", ProgrammeCardEmailView.as_view(), name="admin-id-programme-card-email"),
    path(f"{_CARD}/photo", ProgrammeCardStaffPhotoView.as_view(), name="admin-id-programme-card-photo"),
    path(f"{_CARD}/photo-request", ProgrammeCardPhotoRequestView.as_view(),
         name="admin-id-programme-card-photo-request"),
]
