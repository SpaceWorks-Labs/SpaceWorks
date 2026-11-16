"""UNMOUNTED C2 contract proposals; G owns approval and shared registries."""
from django.urls import path
from . import views_configuration as c, views_completion as v

B = "events/<int:pk>/"
N = "events-programme-admin-"
urlpatterns = [
    path(B + "mentor-profiles/<int:assignment_id>/", c.MentorProfileView.as_view(), name=N + "mentor-profiles"),
    path(B + "help-types/", c.HelpTypesView.as_view(), name=N + "help-types-list"),
    path(B + "help-types/<int:type_id>/", c.HelpTypeDetailView.as_view(), name=N + "help-types-detail"),
    path(B + "mentor-conflicts/", c.ConflictView.as_view(), name=N + "mentor-conflicts"),
    path(B + "mentor-attention/mute/", c.MuteView.as_view(), name=N + "mentor-attention-mute"),
    path(B + "mentor-rounds/<int:round_id>/nominations/", c.NominationView.as_view(), name=N + "mentor-rounds-nominations"),
    path(B + "help/<int:help_id>/renew/", c.RenewHelpView.as_view(), name=N + "help-renew"),
    path(B + "mentor-assignments/<int:assignment_id>/activate/", v.AssignmentActivateView.as_view(), name=N + "mentor-assignments-activate"),
    path(B + "mentor-assignments/<int:assignment_id>/end/", v.AssignmentEndView.as_view(), name=N + "mentor-assignments-end"),
    path(B + "teams-export/", v.TeamExportView.as_view(), name=N + "teams-export"),
]
