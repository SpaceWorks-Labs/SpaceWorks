"""Ready to install under /api/v1/public/; D supplies live gallery predicates."""
from django.urls import path
from .views_downloads import GalleryAssetView

urlpatterns = [path("event-programmes/<uuid:public_token>/gallery/assets/<uuid:public_asset_id>/",
    GalleryAssetView.as_view(), name="events-programme-public-gallery-assets")]
