from django.urls import path
from .views_member import (StageFormListView, StageFormContextView, StageDraftView,
                           StageResponseView, StageResponseSubmitView)

urlpatterns = [
    path("stage-forms/", StageFormListView.as_view(), name="member-event-stage-form-list"),
    path("stage-forms/<int:stage_form_id>/context/", StageFormContextView.as_view(), name="member-event-stage-form-context"),
    path("stage-forms/<int:stage_form_id>/draft/", StageDraftView.as_view(), name="member-event-stage-draft"),
    path("stage-responses/<int:response_id>/", StageResponseView.as_view(), name="member-event-stage-response"),
    path("stage-responses/<int:response_id>/submit/", StageResponseSubmitView.as_view(), name="member-event-stage-response-submit"),
]
