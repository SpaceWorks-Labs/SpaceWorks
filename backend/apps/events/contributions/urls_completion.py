"""UNMOUNTED C2 contract proposals. G must add fixture/registry entries first."""
from django.urls import path
from . import views_completion as v

ADMIN = [
    path("events/<int:pk>/roles/<int:assignment_id>/complete/", v.RoleCompletionView.as_view(), name="events-programme-admin-roles-complete"),
    path("events/<int:pk>/roles/<int:assignment_id>/reject/", v.RoleRejectView.as_view(), name="events-programme-admin-roles-reject"),
    path("events/<int:pk>/roles/<int:assignment_id>/reopen-answers/", v.RoleReopenView.as_view(), name="events-programme-admin-roles-reopen-answers"),
    path("events/<int:pk>/roles/<int:assignment_id>/reconfirm/", v.RoleReconfirmView.as_view(), name="events-programme-admin-roles-reconfirm"),
    path("events/<int:pk>/roles/<int:assignment_id>/requirement-overrides/", v.RequirementOverrideView.as_view(), name="events-programme-admin-roles-requirement-overrides"),
    path("events/<int:pk>/roles/<int:assignment_id>/admit/", v.ContributorAdmissionView.as_view(), name="events-programme-admin-roles-admit"),
]
M = "makerspaces/<int:makerspace_id>/events/<int:pk>/role-applications/<int:assignment_id>/"
MEMBER = [
    path(M + "decline/", v.RoleDeclineView.as_view(), name="events-programme-member-role-application-decline"),
    path(M + "export/", v.RoleOwnerExportView.as_view(), name="events-programme-member-role-application-export"),
]
