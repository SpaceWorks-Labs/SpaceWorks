from django.urls import path
from .views_confirmation import (BookingConfirmationView, BookingConfirmationPngView,
    BookingConfirmationCalendarView, BookingCredentialRotateView)

from .views_passes import BookingMemberPassView

urlpatterns = [
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/pass.pdf", BookingMemberPassView.as_view(), name="member-booking-pass"),
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/confirmation/", BookingConfirmationView.as_view(), name="member-booking-confirmation"),
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/confirmation.png", BookingConfirmationPngView.as_view(), name="member-booking-confirmation-png"),
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/calendar.ics", BookingConfirmationCalendarView.as_view(), name="member-booking-calendar"),
    path("<slug:makerspace_slug>/my-bookings/<uuid:public_token>/rotate-checkin/", BookingCredentialRotateView.as_view(), name="member-booking-rotate-checkin"),
]
