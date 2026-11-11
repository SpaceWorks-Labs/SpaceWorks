from django.urls import path

from apps.organizations.views_public import (
    PublicOrganizationDetailView,
)
from apps.organizations.views_public_directory import PublicOrganizationDirectoryView
from apps.separability.registry import runtime_active


def _events_routes():
    """The one route in this urlconf that serves a SEPARABLE app.

    `organizations` is not separable, so this module is included unconditionally -- but
    a tombstone has to remove the surface, not merely empty its response. Without this
    gate the OpenAPI schema kept advertising `/events/` on a deployment with the events
    app tombstoned. `public_events_for` keeps its own `runtime_active` guard as depth.
    """
    if not runtime_active("events"):
        return []
    from .views_public_events import PublicOrganizationEventListView
    return [
        path(
            "<slug:slug>/events/",
            PublicOrganizationEventListView.as_view(),
            name="public-organization-events",
        )
    ]


urlpatterns = [
    path("", PublicOrganizationDirectoryView.as_view(), name="public-organization-directory"),
    path("<slug:slug>/", PublicOrganizationDetailView.as_view(), name="public-organization-detail"),
    *_events_routes(),
]
