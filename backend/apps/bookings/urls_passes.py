from django.urls import path

from .views_passes import BookingPassPreviewView, BookingPassTemplateView, BookingStaffPassView

urlpatterns = [
    path("spaces/<int:pk>/pass-template/", BookingPassTemplateView.as_view(), name="admin-booking-pass-template"),
    path("spaces/<int:pk>/pass-preview/", BookingPassPreviewView.as_view(), name="admin-booking-pass-preview"),
    path("spaces/<int:pk>/arrival/<int:booking_id>/pass/", BookingStaffPassView.as_view(), name="admin-booking-pass"),
]
