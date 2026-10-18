from django.urls import path
from . import views_admin as v

urlpatterns = [
    path("reimbursements/programme/", v.ProgrammeView.as_view(), name="admin-event-reimbursement-programme"),
    path("reimbursements/requests/", v.RequestListView.as_view(), name="admin-event-reimbursement-request-list"),
    path("reimbursements/requests/<int:request_id>/decide/", v.AwardDecisionView.as_view(), name="admin-event-reimbursement-request-decide"),
    path("reimbursements/claims/", v.ClaimListView.as_view(), name="admin-event-reimbursement-claim-list"),
    path("reimbursements/claims/<int:claim_id>/", v.ClaimDetailView.as_view(), name="admin-event-reimbursement-claim-detail"),
    path("reimbursements/claims/<int:claim_id>/review/", v.ClaimReviewView.as_view(), name="admin-event-reimbursement-claim-review"),
    path("reimbursements/claims/<int:claim_id>/extend/", v.ClaimExtendView.as_view(), name="admin-event-reimbursement-claim-extend"),
    path("reimbursements/claims/<int:claim_id>/attendance-attestations/", v.AttendanceAttestView.as_view(), name="admin-event-reimbursement-attendance-attest"),
    path("reimbursements/claims/<int:claim_id>/receipt-allocation-overrides/", v.ReceiptOverrideView.as_view(), name="admin-event-reimbursement-receipt-override"),
    path("reimbursements/claims/<int:claim_id>/correct-decision/", v.CorrectDecisionView.as_view(), name="admin-event-reimbursement-claim-correct-decision"),
]
