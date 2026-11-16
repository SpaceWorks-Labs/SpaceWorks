from django.urls import path
from .views_broadcasts import BookingBroadcastActionView, BookingBroadcastListView

urlpatterns = [
    path("spaces/<int:pk>/broadcasts/", BookingBroadcastListView.as_view(), name="admin-booking-broadcasts"),
    path("spaces/<int:pk>/broadcasts/<int:campaign_id>/queue/", BookingBroadcastActionView.as_view(),
         name="admin-booking-broadcast-queue"),
    path("spaces/<int:pk>/broadcasts/<int:campaign_id>/cancel/", BookingBroadcastActionView.as_view(action="cancel"),
         name="admin-booking-broadcast-cancel"),
]
