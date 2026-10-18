from django.urls import path
from . import views_member as v

urlpatterns = [
    path("", v.MemberPayoutListView.as_view(), name="member-event-payout-list"),
    path("<uuid:obligation_id>/", v.MemberPayoutDetailView.as_view(), name="member-event-payout-detail"),
    path("<uuid:obligation_id>/payee/", v.MemberPayeeView.as_view(), name="member-event-payout-payee"),
    path("<uuid:obligation_id>/payee/reveal/", v.MemberPayeeRevealView.as_view(), name="member-event-payee-reveal"),
]
