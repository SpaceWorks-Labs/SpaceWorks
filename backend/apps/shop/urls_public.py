"""Public shop routes (mounted under api/v1/public/)."""

from django.urls import path

from . import views_event_offers as e
from . import views_public as v

urlpatterns = [
    path("m/<str:makerspace_slug>/shop/", v.PublicShopView.as_view(), name="public-shop"),
    path("m/<str:makerspace_slug>/shop/products/", v.PublicProductListView.as_view(), name="public-shop-products"),
    path("m/<str:makerspace_slug>/shop/products/<slug:product_slug>/", v.PublicProductDetailView.as_view(),
         name="public-shop-product"),
    path("m/<str:makerspace_slug>/shop/quote/", v.PublicShopQuoteView.as_view(), name="public-shop-quote"),
    path("m/<str:makerspace_slug>/shop/email-code/", v.PublicShopEmailCodeView.as_view(),
         name="public-shop-email-code"),
    path("m/<str:makerspace_slug>/shop/orders/", v.PublicShopOrderView.as_view(), name="public-shop-orders"),
    path("m/<str:makerspace_slug>/shop/orders/<str:token>/", v.PublicShopOrderStatusView.as_view(),
         name="public-shop-order-status"),
    path("m/<str:makerspace_slug>/shop/events/<uuid:public_token>/offers/", e.PublicShopEventOffersView.as_view(),
         name="public-shop-event-offers"),
]
