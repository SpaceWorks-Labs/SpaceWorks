"""Parity E-B7 insight routes. Mounted under `admin/` by `events/urls_programme.py`; each name is catalogued
in `accounts/programme_route_catalog_e_b7.py`."""
from django.urls import path

from .programme.views_insights import OrganizationEventInsightsView, SpaceEventInsightsView

P = "events-programme-admin-"
ADMIN = [
    path("events/insights/", SpaceEventInsightsView.as_view(), name=P + "space-insights"),
    path("organizations/<int:pk>/events/insights/", OrganizationEventInsightsView.as_view(),
         name=P + "organization-insights"),
]
