"""Phase 2 bookings routes: place gallery, requests queue, decisions, departures, issues, venue."""

from django.urls import path

from .views_gallery import SpacePhotoDetailView, SpacePhotoListView, SpacePhotoOrderView, SpacePhotoPresignView
from .views_queue import (
    BookingDepartView, BookingIssueListView, BookingIssueResolveView, BookingQueueView, MemberBookingCheckoutView,
)
from .views_venue import PublicEventVenueView

admin_patterns = [
    path("spaces/<int:pk>/photos/", SpacePhotoListView.as_view(), name="admin-bookable-space-photos"),
    path("spaces/<int:pk>/photos/presign/", SpacePhotoPresignView.as_view(), name="admin-bookable-space-photo-presign"),
    path("spaces/<int:pk>/photos/order/", SpacePhotoOrderView.as_view(), name="admin-bookable-space-photo-order"),
    path("spaces/<int:pk>/photos/<int:photo_id>/", SpacePhotoDetailView.as_view(), name="admin-bookable-space-photo"),
    path("makerspaces/<int:makerspace_id>/bookings/", BookingQueueView.as_view(), name="admin-makerspace-booking-queue"),
    path("makerspaces/<int:makerspace_id>/booking-issues/", BookingIssueListView.as_view(), name="admin-booking-issues"),
    path("booking-issues/<int:pk>/resolve/", BookingIssueResolveView.as_view(), name="admin-booking-issue-resolve"),
    path("spaces/<int:pk>/arrival/<int:booking_id>/depart/", BookingDepartView.as_view(), name="admin-booking-arrival-depart"),
]

public_patterns = [
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/checkout/", MemberBookingCheckoutView.as_view(),
         name="member-booking-checkout"),
    path("<slug:makerspace_slug>/events/<uuid:public_token>/venue/", PublicEventVenueView.as_view(),
         name="public-event-venue"),
]
