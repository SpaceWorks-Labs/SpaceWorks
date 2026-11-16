from django.urls import path

from .views_integration import (
    IntegrationBookingDetailView, IntegrationBookingListView,
    IntegrationBookingResourceDetailView, IntegrationBookingResourceListView,
    IntegrationBookingResourceReservationsView,
)

urlpatterns = [
    path("resources/", IntegrationBookingResourceListView.as_view(), name="integration-booking-resource-list"),
    path("resources/<int:pk>/", IntegrationBookingResourceDetailView.as_view(), name="integration-booking-resource-detail"),
    path("resources/<int:pk>/bookings/", IntegrationBookingResourceReservationsView.as_view(),
         name="integration-booking-resource-reservations"),
    path("bookings/", IntegrationBookingListView.as_view(), name="integration-booking-list"),
    path("bookings/<int:pk>/", IntegrationBookingDetailView.as_view(), name="integration-booking-detail"),
]
