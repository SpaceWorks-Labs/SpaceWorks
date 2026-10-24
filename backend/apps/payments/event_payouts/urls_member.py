from django.urls import path
from . import views_member as v
from . import views_files as f

urlpatterns = [
    path("", v.MemberPayoutListView.as_view(), name="member-event-payout-list"),
    path("<uuid:obligation_id>/", v.MemberPayoutDetailView.as_view(), name="member-event-payout-detail"),
    path("<uuid:obligation_id>/payee/", v.MemberPayeeView.as_view(), name="member-event-payout-payee"),
    path("<uuid:obligation_id>/payee/reveal/", v.MemberPayeeRevealView.as_view(), name="member-event-payee-reveal"),
    path("<uuid:obligation_id>/payee-files/", f.PayeeFileCreateView.as_view(), name="member-event-payee-file-create"),
    path("<uuid:obligation_id>/payee-files/<int:asset_id>/", f.PayeeFileDetailView.as_view(), name="member-event-payee-file-detail"),
    path("<uuid:obligation_id>/payee-files/<int:asset_id>/complete/", f.PayeeFileCompleteView.as_view(), name="member-event-payee-file-complete"),
]
