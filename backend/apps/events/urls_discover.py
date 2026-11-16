"""Public discovery helpers owned by events (spliced under `api/v1/discover/` while events is installed)."""
from django.urls import path

from .views_discover_organizers import WebsiteDiscoverOrganizersView

urlpatterns = [
    path("events/organizers/", WebsiteDiscoverOrganizersView.as_view(), name="website-discover-organizers"),
]
