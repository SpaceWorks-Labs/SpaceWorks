"""Member and public routes of the release-2 membership lifecycle (lane L4)."""
from django.urls import path

from apps.makerspaces.views_membership_member_l4 import (
    MemberConsentView, MemberErasureRequestView, MemberErasureWithdrawView, MemberHistoryView,
    MemberRefundSuggestionView,
)
from apps.makerspaces.views_public_plans import PublicInviteLinkView, PublicPlanDetailView, PublicPlanListView

_MEMBER = "member/makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_MEMBER}/consents", MemberConsentView.as_view(), name="member-membership-consents"),
    path(f"{_MEMBER}/erasure-requests", MemberErasureRequestView.as_view(), name="member-erasure-requests"),
    path(f"{_MEMBER}/erasure-requests/<int:request_id>/withdraw", MemberErasureWithdrawView.as_view(),
         name="member-erasure-request-withdraw"),
    path(f"{_MEMBER}/membership-history", MemberHistoryView.as_view(), name="member-membership-history"),
    path(f"{_MEMBER}/payments/<int:payment_id>/refund-suggestion", MemberRefundSuggestionView.as_view(),
         name="member-refund-suggestion"),
    path("public/<slug:makerspace_slug>/membership-plans", PublicPlanListView.as_view(), name="public-membership-plans"),
    path("public/<slug:makerspace_slug>/membership-plans/<slug:plan_slug>", PublicPlanDetailView.as_view(),
         name="public-membership-plan-detail"),
    path("public/<slug:makerspace_slug>/membership-invites/<str:code>", PublicInviteLinkView.as_view(),
         name="public-membership-invite"),
]
