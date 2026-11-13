"""Decision 223: the staff guest-pass desk and the Space Manager's policy and products."""
from django.urls import path

from apps.admin_api.views_guest_pass_settings import (
    DayPassProductArchiveView, DayPassProductDetailView, DayPassProductListView, GuestPassPolicyView,
)
from apps.admin_api.views_guest_passes import (
    GuestPassDeskSaleView, GuestPassDeskWaiverView, GuestPassListView, GuestPassRevokeView,
)

_SPACE = "makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_SPACE}/guest-passes", GuestPassListView.as_view(), name="admin-guest-passes"),
    path(f"{_SPACE}/guest-passes/sell", GuestPassDeskSaleView.as_view(), name="admin-guest-pass-sale"),
    path(f"{_SPACE}/guest-passes/<int:pass_id>/revoke", GuestPassRevokeView.as_view(), name="admin-guest-pass-revoke"),
    path(f"{_SPACE}/guest-passes/<int:pass_id>/waiver", GuestPassDeskWaiverView.as_view(),
         name="admin-guest-pass-waiver"),
    path(f"{_SPACE}/guest-pass-policy", GuestPassPolicyView.as_view(), name="admin-guest-pass-policy"),
    path(f"{_SPACE}/day-pass-products", DayPassProductListView.as_view(), name="admin-day-pass-products"),
    path(f"{_SPACE}/day-pass-products/<int:product_id>", DayPassProductDetailView.as_view(),
         name="admin-day-pass-product"),
    path(f"{_SPACE}/day-pass-products/<int:product_id>/archive", DayPassProductArchiveView.as_view(),
         name="admin-day-pass-product-archive"),
]
