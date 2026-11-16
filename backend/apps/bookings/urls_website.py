from django.urls import path
from .views_website_admin import (
    BookingWebsiteView, BookingWebsiteReleaseView, BookingWebsiteAssetView, BookingWebsiteAssetDetailView,
)
from .views_website_public import PublicBookingResourceView, PublicBookingWebsiteView, PublicBookingWebsiteImageView

admin_patterns = [
    path("spaces/<int:pk>/website/", BookingWebsiteView.as_view(), name="admin-booking-website"),
    path("spaces/<int:pk>/website/release/", BookingWebsiteReleaseView.as_view(), name="admin-booking-website-release"),
    path("spaces/<int:pk>/website/assets/", BookingWebsiteAssetView.as_view(), name="admin-booking-website-assets"),
    path("spaces/<int:pk>/website/assets/<int:asset_id>/", BookingWebsiteAssetDetailView.as_view(), name="admin-booking-website-asset"),
]
public_patterns = [
    path("<slug:makerspace_slug>/spaces/<uuid:public_token>/", PublicBookingResourceView.as_view(), name="public-booking-resource"),
    path("<slug:makerspace_slug>/spaces/<uuid:public_token>/website/", PublicBookingWebsiteView.as_view(), name="public-booking-website"),
    path("<slug:makerspace_slug>/spaces/<uuid:public_token>/website/assets/<int:asset_id>/", PublicBookingWebsiteImageView.as_view(), name="public-booking-website-image"),
]
