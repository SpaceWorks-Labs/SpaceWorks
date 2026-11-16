from django.urls import path
from .website_views import (
    WebsiteEmbedView, WebsiteShareView, WebsiteDiscoverView, WebsiteSitemapView, WebsiteRobotsView,
)
from apps.operations.views_legal import PublicLegalPageView
from .website_settings_views import WebsiteOriginsView

from .public_profile_share import PublicProfileShareView

urlpatterns = [
    path("share/profiles/<str:handle>/", PublicProfileShareView.as_view(), name="public-profile-share"),
    path("embed/<slug:makerspace_slug>/<slug:kind>/<uuid:public_token>/", WebsiteEmbedView.as_view(), name="website-embed"),
    path("share/<slug:kind>/<uuid:public_token>/", WebsiteShareView.as_view(), name="website-share"),
    path("api/v1/discover/legal/<slug:page>/", PublicLegalPageView.as_view(), name="public-legal-page"),
    path("api/v1/discover/<slug:kind>/", WebsiteDiscoverView.as_view(), name="website-discover"),
    path("api/v1/admin/makerspaces/<int:makerspace_id>/website-embed-origins/", WebsiteOriginsView.as_view(), name="website-origins"),
    path("sitemap.xml", WebsiteSitemapView.as_view(), name="website-sitemap"),
    path("robots.txt", WebsiteRobotsView.as_view(), name="website-robots"),
]
