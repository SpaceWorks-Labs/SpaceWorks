"""A buyer's own shop orders (mounted under api/v1/member/)."""

from django.urls import path

from . import views_member as v

urlpatterns = [
    path("shop/orders/", v.MemberShopOrderListView.as_view(), name="member-shop-orders"),
    path("shop/orders/<int:pk>/", v.MemberShopOrderDetailView.as_view(), name="member-shop-order"),
    path("shop/orders/<int:pk>/cancel/", v.MemberShopOrderCancelView.as_view(), name="member-shop-order-cancel"),
]
