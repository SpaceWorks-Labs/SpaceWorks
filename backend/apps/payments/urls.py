"""The payment LEDGER's staff surface. Mounted unconditionally.

Recording, listing and settling money owed is not an online-payment feature: a
deployment that ships no provider rail at all still has members who owe money and staff
who take it at the desk. Only the routes that actually talk to a provider live in
`apps.payments_rail.urls`, where a tombstone can withdraw them.
"""

from django.urls import path

from apps.payments.urls_l5 import L5_PATTERNS
from apps.payments.urls_pricing import PRICING_PATTERNS
from apps.payments.donations.urls import DONATION_PATTERNS  # release 2 L18
from apps.payments.views_member import ArchivedPaymentDiscoveryView
from apps.payments.views_documents import StaffDocumentListView, StaffDocumentGrantView, DocumentDownloadView
from apps.payments.views_billing import BillingSettingsView
from apps.payments.views_event_money import EventMoneySettingsView  # hack-money G7/G13
from apps.payments.views_refunds_offline import PaymentOfflineRefundView, PaymentDepositReleaseView, PaymentRefundAmendView
from apps.payments.views_refund_cases import (
    RefundCaseApproveView, RefundCaseDeclineView, RefundCaseDetailView, RefundCaseListView,
)
from apps.payments.views_refund_policies import RefundPlanPolicyView, RefundPolicyDetailView, RefundPolicyListView
from apps.payments.views_reconciliation import (
    PaymentBulkMarkOfflineView,
    PaymentBulkWaiveView,
    PaymentListView,
    PaymentMarkOfflineView,
    PaymentSettlementAmendView,
    PaymentWaiveView,
)

# Refund cases and policies are ledger core: the queue survives a rail tombstone, where
# an online case can still be declined (R4) and an offline one approved with a receipt.
REFUND_CASE_PATTERNS = [
    path("admin/makerspace/<int:makerspace_id>/refund-cases", RefundCaseListView.as_view(), name="refund-case-list"),
    path("admin/makerspace/<int:makerspace_id>/refund-cases/<int:case_id>", RefundCaseDetailView.as_view(), name="refund-case-detail"),
    path("admin/makerspace/<int:makerspace_id>/refund-cases/<int:case_id>/approve", RefundCaseApproveView.as_view(), name="refund-case-approve"),
    path("admin/makerspace/<int:makerspace_id>/refund-cases/<int:case_id>/decline", RefundCaseDeclineView.as_view(), name="refund-case-decline"),
    path("admin/makerspace/<int:makerspace_id>/refund-policies", RefundPolicyListView.as_view(), name="refund-policy-list"),
    path("admin/makerspace/<int:makerspace_id>/refund-policies/membership/plans/<int:plan_id>", RefundPlanPolicyView.as_view(), name="refund-policy-plan"),
    path("admin/makerspace/<int:makerspace_id>/refund-policies/<str:area>", RefundPolicyDetailView.as_view(), name="refund-policy-detail"),
]

urlpatterns = [
    *REFUND_CASE_PATTERNS,
    *L5_PATTERNS,
    *PRICING_PATTERNS,
    *DONATION_PATTERNS,
    path("admin/makerspace/<int:makerspace_id>/payment-documents", StaffDocumentListView.as_view(), name="staff-payment-documents"),
    path("admin/makerspace/<int:makerspace_id>/payment-documents/<int:document_id>/download-url", StaffDocumentGrantView.as_view(), name="staff-payment-document-url"),
    path("payment-documents/<int:document_id>/download", DocumentDownloadView.as_view(), name="payment-document-download"),
    path("admin/makerspace/<int:makerspace_id>/billing-settings", BillingSettingsView.as_view(), name="payment-billing-settings"),
    path("admin/makerspace/<int:makerspace_id>/event-money-settings", EventMoneySettingsView.as_view(), name="admin-event-money-settings"),
    path("admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/release-deposit", PaymentDepositReleaseView.as_view(), name="payment-deposit-release"),
    path("admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/refunds/<int:refund_id>/amend", PaymentRefundAmendView.as_view(), name="payment-refund-amend"),
    path("admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/refund-offline", PaymentOfflineRefundView.as_view(), name="payment-reconciliation-refund-offline"),
    path(
        "member/archived-payments",
        ArchivedPaymentDiscoveryView.as_view(),
        name="member-archived-payments",
    ),
    path("admin/makerspace/<int:makerspace_id>/payments", PaymentListView.as_view(), name="payment-reconciliation-list"),
    path("admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/mark-offline", PaymentMarkOfflineView.as_view(), name="payment-reconciliation-mark-offline"),
    path("admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/waive", PaymentWaiveView.as_view(), name="payment-reconciliation-waive"),
    path(
        "admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/amend-settlement",
        PaymentSettlementAmendView.as_view(),
        name="payment-settlement-amend",
    ),
    path("admin/makerspace/<int:makerspace_id>/payments/bulk/mark-offline", PaymentBulkMarkOfflineView.as_view(), name="payment-reconciliation-bulk-mark-offline"),
    path("admin/makerspace/<int:makerspace_id>/payments/bulk/waive", PaymentBulkWaiveView.as_view(), name="payment-reconciliation-bulk-waive"),
]
