from django.urls import path
from .views_broadcasts import EventBroadcastListView, EventBroadcastActionView
from .views_bulk_invites import EventBulkInviteView
from .views_event_loans_passes import EventGuestPassesView, EventLoansView  # decision 242(g)

urlpatterns = [
    path("events/<int:pk>/broadcasts/", EventBroadcastListView.as_view(), name="admin-event-broadcasts"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/queue/", EventBroadcastActionView.as_view(action="queue"), name="admin-event-broadcast-queue"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/cancel/", EventBroadcastActionView.as_view(action="cancel"), name="admin-event-broadcast-cancel"),
    path("events/<int:pk>/invites/bulk/", EventBulkInviteView.as_view(), name="admin-event-bulk-invites"),
    path("events/<int:pk>/loans/", EventLoansView.as_view(), name="admin-event-loans"),
    path("events/<int:pk>/guest-passes/", EventGuestPassesView.as_view(), name="admin-event-guest-passes"),
]
