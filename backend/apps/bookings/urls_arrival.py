from django.urls import path
from .views_arrival import BookingArrivalResolveView, BookingArrivalConfirmView, BookingArrivalReverseView

urlpatterns = [
    path("spaces/<int:pk>/arrival/resolve/", BookingArrivalResolveView.as_view(), name="admin-booking-arrival-resolve"),
    path("spaces/<int:pk>/arrival/confirm/", BookingArrivalConfirmView.as_view(), name="admin-booking-arrival-confirm"),
    path("spaces/<int:pk>/arrival/<int:booking_id>/reverse/", BookingArrivalReverseView.as_view(), name="admin-booking-arrival-reverse"),
]
