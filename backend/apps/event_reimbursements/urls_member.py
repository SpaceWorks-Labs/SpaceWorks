from django.urls import path
from . import views_member as v
from . import views_receipts as files

urlpatterns = [
    path("reimbursement/", v.ReimbursementView.as_view(), name="member-event-reimbursement"),
    path("reimbursement/request/submit/", v.RequestSubmitView.as_view(), name="member-event-reimbursement-request-submit"),
    path("reimbursement/request/withdraw/", v.RequestWithdrawView.as_view(), name="member-event-reimbursement-request-withdraw"),
    path("reimbursement/award/accept/", v.AwardAcceptView.as_view(), name="member-event-reimbursement-award-accept"),
    path("reimbursement/award/decline/", v.AwardDeclineView.as_view(), name="member-event-reimbursement-award-decline"),
    path("reimbursement/claim/", v.ClaimView.as_view(), name="member-event-reimbursement-claim"),
    path("reimbursement/claim/submit/", v.ClaimSubmitView.as_view(), name="member-event-reimbursement-claim-submit"),
    path("reimbursement/claim/appeal/", v.ClaimAppealView.as_view(), name="member-event-reimbursement-claim-appeal"),
    path("reimbursement/receipt-files/", files.ReceiptCreateView.as_view(), name="member-event-receipt-file-create"),
    path("reimbursement/receipt-files/<int:asset_id>/", files.ReceiptDetailView.as_view(), name="member-event-receipt-file-detail"),
    path("reimbursement/receipt-files/<int:asset_id>/complete/", files.ReceiptCompleteView.as_view(), name="member-event-receipt-file-complete"),
]
