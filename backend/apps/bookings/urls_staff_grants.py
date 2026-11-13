from django.urls import path

from .views_accessible_spaces import AccessibleSpaceListView
from .views_staff_grants import (
    BookingStaffGrantDetailView, BookingStaffGrantListView, BookingStaffGrantRevokeView,
    BookingStaffInviteListView, BookingStaffInviteRedeemView, BookingStaffInviteRevokeView,
)

urlpatterns = [
    path("accessible-booking-spaces/", AccessibleSpaceListView.as_view(), name="admin-accessible-booking-spaces"),
    path("spaces/<int:pk>/staff-grants/", BookingStaffGrantListView.as_view(), name="admin-booking-staff-grants"),
    path("spaces/<int:pk>/staff-invites/", BookingStaffInviteListView.as_view(), name="admin-booking-staff-invites"),
    path("booking-staff-grants/<int:pk>/", BookingStaffGrantDetailView.as_view(), name="admin-booking-staff-grant-detail"),
    path("booking-staff-grants/<int:pk>/revoke/", BookingStaffGrantRevokeView.as_view(), name="admin-booking-staff-grant-revoke"),
    path("booking-staff-invites/<int:pk>/revoke/", BookingStaffInviteRevokeView.as_view(), name="admin-booking-staff-invite-revoke"),
    path("booking-staff-invites/redeem/", BookingStaffInviteRedeemView.as_view(), name="booking-staff-invite-redeem"),
]
