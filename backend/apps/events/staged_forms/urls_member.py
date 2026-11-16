from django.urls import path
from .views_member import (StageFormListView, StageFormContextView, StageDraftView,
                           StageResponseView, StageResponseSubmitView)
from .views_uploads import (StageFileCreateView, StageFileDetailView, StageFileCompleteView, StageFileDownloadView)

urlpatterns = [
    path("stage-forms/", StageFormListView.as_view(), name="member-event-stage-form-list"),
    path("stage-forms/<int:stage_form_id>/context/", StageFormContextView.as_view(), name="member-event-stage-form-context"),
    path("stage-forms/<int:stage_form_id>/draft/", StageDraftView.as_view(), name="member-event-stage-draft"),
    path("stage-responses/<int:response_id>/", StageResponseView.as_view(), name="member-event-stage-response"),
    path("stage-responses/<int:response_id>/submit/", StageResponseSubmitView.as_view(), name="member-event-stage-response-submit"),
    path("stage-forms/<int:stage_form_id>/files/", StageFileCreateView.as_view(), name="member-event-stage-file-create"),
    path("stage-forms/<int:stage_form_id>/files/<int:asset_id>/", StageFileDetailView.as_view(), name="member-event-stage-file-detail"),
    path("stage-forms/<int:stage_form_id>/files/<int:asset_id>/complete/", StageFileCompleteView.as_view(), name="member-event-stage-file-complete"),
    path("stage-forms/<int:stage_form_id>/files/<int:asset_id>/download/", StageFileDownloadView.as_view(), name="member-event-stage-file-download"),
]
