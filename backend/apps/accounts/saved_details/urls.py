"""Mount at /api/v1/member/saved-details/; integration owns protected registries."""
from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.DetailsView.as_view(), name="member-saved-details-list"),
    path("prefill/", v.PrefillView.as_view(), name="member-saved-details-prefill"),
    path("save-intents/<uuid:operation_uuid>/", v.IntentView.as_view(), name="member-saved-detail-intent-detail"),
    path("resume-assets/", v.ResumeCreateView.as_view(), name="member-saved-resume-create"),
    path("resume-assets/<int:asset_id>/", v.ResumeDetailView.as_view(), name="member-saved-resume-detail"),
    path("resume-assets/<int:asset_id>/complete/", v.ResumeCompleteView.as_view(), name="member-saved-resume-complete"),
    path("resume-assets/<int:asset_id>/download/", v.ResumeDownloadView.as_view(), name="member-saved-resume-download"),
    path("export/", v.ExportCreateView.as_view(), name="member-saved-details-export-create"),
    path("export/<uuid:job_uuid>/", v.ExportDetailView.as_view(), name="member-saved-details-export-detail"),
    path("export/<uuid:job_uuid>/download/", v.ExportDownloadView.as_view(), name="member-saved-details-export-download"),
    path("<str:field_key>/", v.DetailView.as_view(), name="member-saved-detail-detail"),
]
