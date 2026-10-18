"""L3 attaches these only after classifying every route's origin/client/claim scope."""

from django.urls import path
from .public_page_views import PublicHandleView, PublicPageView
from .public_page_asset_views import PublicPageAssetView

urlpatterns = [
    path("public/page-handles/<str:handle>/", PublicHandleView.as_view(), name="public-page-handle"),
    path("public/<slug:makerspace_slug>/page/", PublicPageView.as_view(), name="public-makerspace-page"),
    path("public/<slug:makerspace_slug>/page/assets/<int:asset_id>/", PublicPageAssetView.as_view(), name="public-makerspace-page-asset"),
    path("public/organizations/<slug:slug>/page/", PublicPageView.as_view(), {"kind": "organization"}, name="public-organization-page"),
    path("public/organizations/<slug:slug>/page/assets/<int:asset_id>/", PublicPageAssetView.as_view(), {"kind": "organization"}, name="public-organization-page-asset"),
]
