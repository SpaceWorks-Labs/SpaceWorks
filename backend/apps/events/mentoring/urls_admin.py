from django.urls import path
from . import views_help as h, views_operations as o

B = "events/<int:pk>/"
N = "events-programme-admin-"
urlpatterns = [
    path(B + "help/", h.AdminHelpCollectionView.as_view(), name=N + "help-collection"),
    path(B + "help/<int:help_id>/", h.AdminHelpDetailView.as_view(), name=N + "help-detail"),
    path(B + "help/<int:help_id>/comments/", h.AdminHelpCommentsView.as_view(), name=N + "help-comments"),
    path(B + "help/<int:help_id>/claim/", h.AdminHelpClaimView.as_view(), name=N + "help-claim"),
    path(B + "help/<int:help_id>/release/", h.AdminHelpReleaseView.as_view(), name=N + "help-release"),
    path(B + "help/<int:help_id>/resolve/", h.AdminHelpResolveView.as_view(), name=N + "help-resolve"),
    path(B + "help/<int:help_id>/reopen/", h.AdminHelpReopenView.as_view(), name=N + "help-reopen"),
    path(B + "help/<int:help_id>/assign/", h.AdminHelpAssignView.as_view(), name=N + "help-assign"),
    path(B + "mentor-assignments/", o.AssignmentsView.as_view(), name=N + "mentor-assignments-list"),
    path(B + "mentor-assignments/preview/", o.AssignmentPreviewView.as_view(), name=N + "mentor-assignments-preview"),
    path(B + "mentor-assignments/assign/", o.AssignmentRunView.as_view(), name=N + "mentor-assignments-assign"),
    path(B + "mentor-rounds/", o.RoundsView.as_view(), name=N + "mentor-rounds-list"),
    path(B + "mentor-rounds/<int:round_id>/", o.RoundDetailView.as_view(), name=N + "mentor-rounds-detail"),
    path(B + "mentor-rounds/<int:round_id>/open/", o.RoundOpenView.as_view(), name=N + "mentor-rounds-open"),
    path(B + "mentor-rounds/<int:round_id>/close/", o.RoundCloseView.as_view(), name=N + "mentor-rounds-close"),
    path(B + "mentor-rounds/<int:round_id>/skip/", o.RoundSkipView.as_view(), name=N + "mentor-rounds-skip"),
    path(B + "mentor-rounds/<int:round_id>/teams/<int:team_id>/claim/", o.RoundClaimView.as_view(), name=N + "mentor-rounds-teams-claim"),
    path(B + "mentor-rounds/<int:round_id>/teams/<int:team_id>/heartbeat/", o.RoundHeartbeatView.as_view(), name=N + "mentor-rounds-teams-heartbeat"),
    path(B + "mentor-rounds/<int:round_id>/teams/<int:team_id>/submit/", o.RoundSubmitView.as_view(), name=N + "mentor-rounds-teams-submit"),
    path(B + "mentor-rounds/<int:round_id>/teams/<int:team_id>/release/", o.RoundReleaseView.as_view(), name=N + "mentor-rounds-teams-release"),
    path(B + "mentor-analytics/", o.AnalyticsView.as_view(), name=N + "mentor-analytics"),
    path(B + "teams-import/preview/", o.ImportPreviewView.as_view(), name=N + "teams-import-preview"),
    path(B + "teams-import/commit/", o.ImportCommitView.as_view(), name=N + "teams-import-commit"),
]
