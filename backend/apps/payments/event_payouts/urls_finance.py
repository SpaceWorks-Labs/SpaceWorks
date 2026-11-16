from django.urls import path
from . import views_finance as v
from .views_files import FinanceAttachmentDownloadView

urlpatterns = [
    path("", v.FinancePayoutListView.as_view(), name="finance-event-payout-list"),
    path("dashboard/", v.PayoutDashboardView.as_view(), name="finance-event-payout-dashboard"),
    path("exports/", v.ExportPayoutView.as_view(), name="finance-event-payout-export"),
    path("exports/<uuid:batch_id>/download/", v.DownloadExportView.as_view(), name="finance-event-payout-export-download"),
    path("<uuid:obligation_id>/", v.FinancePayoutDetailView.as_view(), name="finance-event-payout-detail"),
    path("<uuid:obligation_id>/record/", v.RecordPayoutView.as_view(), name="finance-event-payout-record"),
    path("entries/<uuid:entry_id>/amend/", v.AmendPayoutView.as_view(), name="finance-event-payout-amend"),
    path("<uuid:obligation_id>/cancel/", v.CancelPayoutView.as_view(), name="finance-event-payout-cancel"),
    path("<uuid:obligation_id>/payee/verify/", v.VerifyPayeeView.as_view(), name="finance-event-payee-verify"),
    path("<uuid:obligation_id>/payee/request-correction/", v.CorrectPayeeView.as_view(), name="finance-event-payee-request-correction"),
    path("<uuid:obligation_id>/payee/reveal/", v.RevealPayeeView.as_view(), name="finance-event-payee-reveal"),
    path("<uuid:obligation_id>/hold/", v.HoldPayoutView.as_view(), name="finance-event-payout-hold"),
    path("<uuid:obligation_id>/release-hold/", v.ReleaseHoldView.as_view(), name="finance-event-payout-release-hold"),
    path("<uuid:obligation_id>/acknowledge-eligibility/", v.AcknowledgeEligibilityView.as_view(), name="finance-event-payout-acknowledge-eligibility"),
    path("attachments/<int:asset_id>/download/", FinanceAttachmentDownloadView.as_view(), name="finance-event-attachment-download"),
]
