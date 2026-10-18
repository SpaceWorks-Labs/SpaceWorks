from django.urls import path
from . import views_admin as v
from . import serializers as s

urlpatterns = [
    path("stage-forms/", v.StageDefinitionListView.as_view(), name="admin-event-stage-form-list"),
    path("stage-forms/<int:stage_form_id>/", v.StageDefinitionDetailView.as_view(), name="admin-event-stage-form-detail"),
    path("stage-forms/<int:stage_form_id>/publish/", v.StageTransitionView.as_view(), name="admin-event-stage-form-publish"),
    path("stage-forms/<int:stage_form_id>/retire/", v.StageTransitionView.as_view(publish=False), name="admin-event-stage-form-retire"),
    path("stage-forms/<int:stage_form_id>/activate/", v.StageActivateView.as_view(), name="admin-event-stage-form-activate"),
    path("stage-assignments/", v.StageAssignmentListView.as_view(), name="admin-event-stage-assignment-list"),
    path("stage-assignments/<int:assignment_id>/cancel/", v.StageAssignmentCommandView.as_view(), name="admin-event-stage-assignment-cancel"),
    path("stage-assignments/<int:assignment_id>/reassign/", v.StageAssignmentCommandView.as_view(
        action="reassign", serializer_class=s.ReassignStageAssignmentCommand), name="admin-event-stage-assignment-reassign"),
    path("stage-assignments/<int:assignment_id>/extend/", v.StageAssignmentCommandView.as_view(
        action="extend", serializer_class=s.ExtendStageAssignmentCommand), name="admin-event-stage-assignment-extend"),
    path("stage-assignments/<int:assignment_id>/reopen/", v.StageAssignmentCommandView.as_view(
        action="reopen", serializer_class=s.ExtendStageAssignmentCommand), name="admin-event-stage-assignment-reopen"),
    path("stage-milestones/shortlist/", v.StageShortlistView.as_view(), name="admin-event-stage-shortlist"),
    path("stage-responses/<int:response_id>/", v.StageResponseDetailView.as_view(), name="admin-event-stage-response-detail"),
    path("stage-responses/<int:response_id>/finance/", v.StageResponseFinanceDetailView.as_view(), name="admin-event-stage-response-finance-detail"),
]
