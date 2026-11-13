"""Decision 223: member, sponsor and public guest-pass routes (the staff desk lives in admin_api)."""
from django.urls import path

from apps.makerspaces.views_guest_passes import (
    DayPassPurchaseView, MemberDayPassListView, MyGuestPassesView, MyGuestPassWaiverView, PublicDayPassListView,
    SponsoredGuestRevokeView, SponsoredGuestsView,
)

_MEMBER = "member/makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_MEMBER}/guest-passes", MyGuestPassesView.as_view(), name="member-guest-passes"),
    path(f"{_MEMBER}/guest-passes/<int:pass_id>/accept-waiver", MyGuestPassWaiverView.as_view(),
         name="member-guest-pass-waiver"),
    path(f"{_MEMBER}/guest-passes/sponsored", SponsoredGuestsView.as_view(), name="member-sponsored-guests"),
    path(f"{_MEMBER}/guest-passes/sponsored/<int:pass_id>/revoke", SponsoredGuestRevokeView.as_view(),
         name="member-sponsored-guest-revoke"),
    path(f"{_MEMBER}/day-passes", MemberDayPassListView.as_view(), name="member-day-passes"),
    path(f"{_MEMBER}/day-passes/<int:product_id>/purchase", DayPassPurchaseView.as_view(),
         name="member-day-pass-purchase"),
    path("public/<slug:makerspace_slug>/day-passes", PublicDayPassListView.as_view(), name="public-day-passes"),
]
