"""Badge desk routes under /api/v1/admin/ (parity E-B2); included from `urls_id_cards`."""
from django.urls import path

from .views_badge_prints import EventBadgeDeskView, EventBadgeReceiptsView

urlpatterns = [
    path("events/<int:pk>/badges/desk", EventBadgeDeskView.as_view(), name="admin-event-badge-desk"),
    path("events/<int:pk>/badges/print-receipts", EventBadgeReceiptsView.as_view(),
         name="admin-event-badge-print-receipts"),
]
