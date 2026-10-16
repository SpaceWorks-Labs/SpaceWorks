"""Phase 2 bookings routes: place gallery, requests queue, decisions, departures, issues, venue."""

from django.urls import path

from .views_gallery import SpacePhotoDetailView, SpacePhotoListView, SpacePhotoOrderView, SpacePhotoPresignView
from .views_venue import PublicEventVenueView

admin_patterns = [
    path("spaces/<int:pk>/photos/", SpacePhotoListView.as_view(), name="admin-bookable-space-photos"),
    path("spaces/<int:pk>/photos/presign/", SpacePhotoPresignView.as_view(), name="admin-bookable-space-photo-presign"),
    path("spaces/<int:pk>/photos/order/", SpacePhotoOrderView.as_view(), name="admin-bookable-space-photo-order"),
    path("spaces/<int:pk>/photos/<int:photo_id>/", SpacePhotoDetailView.as_view(), name="admin-bookable-space-photo"),
]

public_patterns = [
    path("<slug:makerspace_slug>/events/<uuid:public_token>/venue/", PublicEventVenueView.as_view(),
         name="public-event-venue"),
]
