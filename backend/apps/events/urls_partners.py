"""Organizer, audience-organization, partner and check-in-list staff routes."""

from django.urls import path

from .views_audience_organizations import EventAudienceOrganizationView
from .views_checkin_history import EventCheckInHistoryView
from .views_directories import OrganizationDirectoryView, PartnerMakerspaceDirectoryView


urlpatterns = [
    # Served by the events app, not `organizations`, so a tombstoned events app takes
    # its only consumer's directory with it. `organizations/<int:pk>/` cannot match it.
    path("organizations/directory/", OrganizationDirectoryView.as_view(),
         name="admin-organization-directory"),
    path("event-partner-makerspaces/", PartnerMakerspaceDirectoryView.as_view(),
         name="admin-event-partner-makerspaces"),
    path("events/<int:pk>/audience-organizations/", EventAudienceOrganizationView.as_view(),
         name="admin-event-audience-organizations"),
    path("events/<int:pk>/check-ins/", EventCheckInHistoryView.as_view(),
         name="admin-event-check-ins"),
]
