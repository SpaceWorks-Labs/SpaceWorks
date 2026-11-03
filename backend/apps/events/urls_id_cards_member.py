"""The registrant's own ticket under /api/v1/member/ (release 2 L3, X49)."""
from django.urls import path

from .id_cards_views_settings import MyTicketView

urlpatterns = [
    path("event-registrations/<int:pk>/ticket", MyTicketView.as_view(), name="member-event-registration-ticket"),
]
