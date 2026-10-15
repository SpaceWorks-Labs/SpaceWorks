from django.urls import path
from .views_website_admin import (
    EventWebsiteView, EventWebsiteReleaseView, EventWebsiteDelayView,
    EventWebsiteAssetView, EventWebsiteAssetDetailView,
)
from .views_website_public import (
    PublicEventWebsiteView, PublicEventWebsiteSectionView, PublicEventWebsiteSessionView,
    PublicEventWebsiteImageView, PublicEventWebsiteScheduleView,
)

admin_patterns = [
    path("events/<int:pk>/website/", EventWebsiteView.as_view(), name="admin-event-website-content"),
    path("events/<int:pk>/website/release/", EventWebsiteReleaseView.as_view(), name="admin-event-website-release"),
    path("events/<int:pk>/website/sessions/<slug:slug>/delay/", EventWebsiteDelayView.as_view(), name="admin-event-website-delay"),
    path("events/<int:pk>/website/assets/", EventWebsiteAssetView.as_view(), name="admin-event-website-assets"),
    path("events/<int:pk>/website/assets/<int:asset_id>", EventWebsiteAssetDetailView.as_view(), name="admin-event-website-asset-detail"),
    path("event-series/<int:pk>/website/", EventWebsiteView.as_view(), {"series": True}, name="admin-series-website-content"),
    path("event-series/<int:pk>/website/release/", EventWebsiteReleaseView.as_view(), {"series": True}, name="admin-series-website-release"),
    path("event-series/<int:pk>/website/sessions/<slug:slug>/delay/", EventWebsiteDelayView.as_view(), {"series": True}, name="admin-series-website-delay"),
    path("event-series/<int:pk>/website/assets/", EventWebsiteAssetView.as_view(), {"series": True}, name="admin-series-website-assets"),
    path("event-series/<int:pk>/website/assets/<int:asset_id>", EventWebsiteAssetDetailView.as_view(), {"series": True}, name="admin-series-website-asset-detail"),
]

base = "<slug:makerspace_slug>/events/<uuid:public_token>/website/"
public_patterns = [
    path(base + "schedule/", PublicEventWebsiteScheduleView.as_view(), name="public-event-website-schedule"),
    path(base + "speakers/<slug:slug>/", PublicEventWebsiteSectionView.as_view(), {"section_kind": "speaker"}, name="public-event-website-speaker"),
    path(base, PublicEventWebsiteView.as_view(), name="public-event-website"),
    path(base + "sections/<slug:slug>/", PublicEventWebsiteSectionView.as_view(), name="public-event-website-section"),
    path(base + "sessions/<slug:slug>/", PublicEventWebsiteSessionView.as_view(), name="public-event-website-session"),
    path(base + "assets/<int:asset_id>/", PublicEventWebsiteImageView.as_view(), name="public-event-website-image"),
]
