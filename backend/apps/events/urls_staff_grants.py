from django.urls import path

from .views_accessible_events import AccessibleEventListView
from .views_staff_grants import (
    EventStaffGrantDetailView, EventStaffGrantListView, EventStaffGrantRevokeView,
    EventStaffInviteListView, EventStaffInviteRedeemView, EventStaffInviteRevokeView,
)

urlpatterns = [
    path("accessible-events/", AccessibleEventListView.as_view(), name="admin-accessible-events"),
    path("events/<int:pk>/staff-grants/", EventStaffGrantListView.as_view(), name="admin-event-staff-grants"),
    path("events/<int:pk>/staff-invites/", EventStaffInviteListView.as_view(), name="admin-event-staff-invites"),
    path("event-series/<int:pk>/staff-grants/", EventStaffGrantListView.as_view(series=True), name="admin-series-staff-grants"),
    path("event-series/<int:pk>/staff-invites/", EventStaffInviteListView.as_view(series=True), name="admin-series-staff-invites"),
    path("event-staff-grants/<int:pk>/", EventStaffGrantDetailView.as_view(), name="admin-event-staff-grant-detail"),
    path("event-staff-grants/<int:pk>/revoke/", EventStaffGrantRevokeView.as_view(), name="admin-event-staff-grant-revoke"),
    path("event-staff-invites/<int:pk>/revoke/", EventStaffInviteRevokeView.as_view(), name="admin-event-staff-invite-revoke"),
    path("event-staff-invites/redeem/", EventStaffInviteRedeemView.as_view(), name="event-staff-invite-redeem"),
]
