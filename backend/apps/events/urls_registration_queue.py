"""Open items A22: the cross-event registration queue (read-only; actions stay per registration)."""
from django.urls import path

from .views_registration_queue import EventRegistrationQueueView

patterns = [
    path("makerspace/<int:makerspace_id>/event-registration-queue", EventRegistrationQueueView.as_view(),
         name="admin-event-registration-queue"),
]
