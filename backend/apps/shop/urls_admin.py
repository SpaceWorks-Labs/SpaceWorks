"""Staff shop routes (mounted under api/v1/admin/)."""

from django.urls import path

from . import views_event_offers as e
from . import views_staff_catalogue as c
from . import views_staff_images as i
from . import views_staff_orders as o
from . import views_staff_pos as p

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/shop/settings/", c.ShopSettingsView.as_view(), name="admin-shop-settings"),
    path("makerspaces/<int:makerspace_id>/shop/products/", c.ShopProductListView.as_view(),
         name="admin-shop-products"),
    path("shop/products/<int:pk>/", c.ShopProductDetailView.as_view(), name="admin-shop-product"),
    path("shop/products/<int:pk>/image/", i.ShopProductImageView.as_view(), name="admin-shop-product-image"),
    path("shop/variants/<int:pk>/", c.ShopVariantDetailView.as_view(), name="admin-shop-variant"),
    path("shop/variants/<int:pk>/stock/", c.ShopVariantStockView.as_view(), name="admin-shop-variant-stock"),
    path("makerspaces/<int:makerspace_id>/shop/movements/", c.ShopMovementListView.as_view(),
         name="admin-shop-movements"),
    path("makerspaces/<int:makerspace_id>/shop/event-offers/", e.ShopEventOfferListView.as_view(),
         name="admin-shop-event-offers"),
    path("makerspaces/<int:makerspace_id>/shop/event-offers/<int:event_id>/", e.ShopEventOfferDetailView.as_view(),
         name="admin-shop-event-offer"),
    path("makerspaces/<int:makerspace_id>/shop/orders/", o.ShopOrderListView.as_view(), name="admin-shop-orders"),
    path("shop/orders/<int:pk>/", o.ShopOrderDetailView.as_view(), name="admin-shop-order"),
    path("shop/orders/<int:pk>/ready/", o.ShopOrderReadyView.as_view(), name="admin-shop-order-ready"),
    path("shop/orders/<int:pk>/move-pickup-to-space/", o.ShopOrderMovePickupView.as_view(),
         name="admin-shop-order-move-pickup-to-space"),
    path("shop/orders/<int:pk>/collect/", o.ShopOrderCollectView.as_view(), name="admin-shop-order-collect"),
    path("shop/orders/<int:pk>/take-payment/", o.ShopOrderTakePaymentView.as_view(),
         name="admin-shop-order-take-payment"),
    path("shop/orders/<int:pk>/cancel/", o.ShopOrderCancelView.as_view(), name="admin-shop-order-cancel"),
    path("shop/orders/<int:pk>/returns/", o.ShopOrderReturnView.as_view(), name="admin-shop-order-returns"),
    path("shop/orders/<int:pk>/receipt/", o.ShopOrderReceiptView.as_view(), name="admin-shop-order-receipt"),
    path("makerspaces/<int:makerspace_id>/shop/pos/quote/", p.ShopPosQuoteView.as_view(), name="admin-shop-pos-quote"),
    path("makerspaces/<int:makerspace_id>/shop/pos/sale/", p.ShopPosSaleView.as_view(), name="admin-shop-pos-sale"),
    path("makerspaces/<int:makerspace_id>/shop/members/", p.ShopMemberLookupView.as_view(),
         name="admin-shop-member-lookup"),
    path("makerspaces/<int:makerspace_id>/shop/report/", p.ShopReportView.as_view(), name="admin-shop-report"),
    path("makerspaces/<int:makerspace_id>/shop/cash-sessions/", p.ShopCashSessionListView.as_view(),
         name="admin-shop-cash-sessions"),
    path("shop/cash-sessions/<int:pk>/close/", p.ShopCashSessionCloseView.as_view(),
         name="admin-shop-cash-session-close"),
    path("shop/cash-sessions/<int:pk>/confirm/", p.ShopCashSessionConfirmView.as_view(),
         name="admin-shop-cash-session-confirm"),
]
