"""Event ID-card and ticket-design organiser routes under /api/v1/admin/ (release 2 L3)."""
from django.urls import path

from apps.card_designs.views_staff_photo import EventCardStaffPhotoView

from .id_cards_views import (EventCardDesignsView, EventCardJobView, EventCardScanView, EventIdCardDetailView,
                             EventIdCardDownloadView, EventIdCardListView, EventIdCardRevokeView)
from .id_cards_preview import EventCardSheetPreviewView
from .id_cards_views_settings import EventCardExtrasView, EventCardSettingsView

urlpatterns = [
    path("events/<int:pk>/card-designs", EventCardDesignsView.as_view(), name="admin-event-card-designs"),
    path("events/<int:pk>/card-settings", EventCardSettingsView.as_view(), name="admin-event-card-settings"),
    path("events/<int:pk>/id-cards", EventIdCardListView.as_view(), name="admin-event-id-cards"),
    path("events/<int:pk>/id-cards/extras", EventCardExtrasView.as_view(), name="admin-event-id-card-extras"),
    path("events/<int:pk>/card-jobs", EventCardJobView.as_view(), name="admin-event-card-jobs"),
    path("events/<int:pk>/card-jobs/preview", EventCardSheetPreviewView.as_view(), name="admin-event-card-job-preview"),
    path("events/<int:pk>/check-in/card-scan", EventCardScanView.as_view(), name="admin-event-card-scan"),
    path("event-id-cards/<int:pk>", EventIdCardDetailView.as_view(), name="admin-event-id-card"),
    path("event-id-cards/<int:pk>/revoke", EventIdCardRevokeView.as_view(), name="admin-event-id-card-revoke"),
    path("event-id-cards/<int:pk>/photo", EventCardStaffPhotoView.as_view(), name="admin-event-id-card-photo"),
    path("event-id-cards/<int:pk>/download", EventIdCardDownloadView.as_view(), name="admin-event-id-card-download"),
]

from .urls_badge_prints import urlpatterns as _badge_patterns  # noqa: E402  (parity E-B2)
urlpatterns += _badge_patterns
