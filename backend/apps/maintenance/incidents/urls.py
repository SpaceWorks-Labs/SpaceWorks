"""Incident register routes: staff at admin_api's `/api/v1/admin/` prefix, members at `/api/v1/`."""

from django.urls import path

from . import views, views_assignees

staff_urlpatterns = [
    path("makerspaces/<int:makerspace_id>/incidents", views.IncidentListView.as_view(), name="admin-incidents"),
    path("incidents/<int:pk>", views.IncidentDetailView.as_view(), name="admin-incident-detail"),
    path("incidents/<int:pk>/actions", views.IncidentActionListView.as_view(), name="admin-incident-actions"),
    path("incidents/<int:pk>/assignees", views_assignees.IncidentAssigneeListView.as_view(),
         name="admin-incident-assignees"),
    path("incident-actions/<int:pk>", views.IncidentActionDetailView.as_view(), name="admin-incident-action-detail"),
]

member_urlpatterns = [
    path("member/makerspaces/<int:makerspace_id>/incidents", views.MemberIncidentView.as_view(),
         name="member-incidents"),
]
