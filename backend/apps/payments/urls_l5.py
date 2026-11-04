"""Lane L5 ledger-core routes: tax, offline claims, maker-checker, capture flags, disputes,
pay links and the finance ledger. Mounted with `apps.payments.urls`, unconditionally:
none talks to a provider (paying a pay link online lives in `apps.payments_rail.urls`)."""

from django.urls import path

from apps.payments import views_finance as finance, views_flags as flags, views_ledger as ledger
from apps.payments import views_offline as offline, views_pay_links as pay, views_tax as tax

SPACE = "admin/makerspace/<int:makerspace_id>"

L5_PATTERNS = [
    path(f"{SPACE}/billing/tax", tax.TaxSettingsView.as_view(), name="billing-tax"),
    path(f"{SPACE}/billing/tax/validate-gstin", tax.GstinValidateView.as_view(), name="billing-tax-gstin"),
    path(f"{SPACE}/billing/tax/preview", tax.TaxPreviewView.as_view(), name="billing-tax-preview"),
    path(f"{SPACE}/billing/tax/gstr1.json", tax.Gstr1JsonView.as_view(), name="billing-tax-gstr1-json"),
    path(f"{SPACE}/paid-claims", offline.StaffClaimListView.as_view(), name="paid-claim-list"),
    path(f"{SPACE}/paid-claims/<int:claim_id>/confirm", offline.StaffClaimConfirmView.as_view(),
         name="paid-claim-confirm"),
    path(f"{SPACE}/paid-claims/<int:claim_id>/reject", offline.StaffClaimRejectView.as_view(),
         name="paid-claim-reject"),
    path(f"{SPACE}/settlements", offline.SettlementConfirmationListView.as_view(), name="settlement-confirmations"),
    path(f"{SPACE}/settlements/<int:confirmation_id>/confirm", offline.SettlementConfirmView.as_view(),
         name="settlement-confirm"),
    path(f"{SPACE}/settlements/<int:confirmation_id>/reject", offline.SettlementRejectView.as_view(),
         name="settlement-reject"),
    path(f"{SPACE}/capture-flags", flags.CaptureFlagListView.as_view(), name="capture-flag-list"),
    path(f"{SPACE}/capture-flags/<int:flag_id>/resolve", flags.CaptureFlagResolveView.as_view(),
         name="capture-flag-resolve"),
    path(f"{SPACE}/disputes", flags.DisputeListView.as_view(), name="dispute-list"),
    path(f"{SPACE}/disputes/<int:dispute_id>", flags.DisputeDetailView.as_view(), name="dispute-detail"),
    path(f"{SPACE}/payments/<int:payment_id>/pay-link", pay.StaffPayLinkView.as_view(), name="payment-pay-link"),
    path(f"{SPACE}/finance/access", ledger.FinanceAccessView.as_view(), name="finance-access"),
    path(f"{SPACE}/finance/summary", finance.FinanceSummaryView.as_view(), name="finance-summary"),
    path(f"{SPACE}/finance/entries", ledger.LedgerEntryListView.as_view(), name="finance-entries"),
    path(f"{SPACE}/finance/entries/<int:entry_id>", ledger.LedgerEntryDetailView.as_view(), name="finance-entry"),
    path(f"{SPACE}/finance/entries/<int:entry_id>/void", ledger.LedgerEntryVoidView.as_view(),
         name="finance-entry-void"),
    path(f"{SPACE}/finance/entries/<int:entry_id>/receipt-url", ledger.ReceiptUrlView.as_view(),
         name="finance-entry-receipt"),
    path(f"{SPACE}/finance/receipt-upload", ledger.ReceiptUploadView.as_view(), name="finance-receipt-upload"),
    path(f"{SPACE}/finance/opening-balances", ledger.OpeningBalanceView.as_view(), name="finance-opening-balances"),
    path(f"{SPACE}/finance/events/<int:event_id>", finance.EventFinanceView.as_view(), name="finance-event"),
    path(f"{SPACE}/finance/events/<int:event_id>/budget", finance.EventBudgetView.as_view(),
         name="finance-event-budget"),
    path("public/pay/<str:token>", pay.PublicPayLinkView.as_view(), name="pay-link"),
    path("public/pay/<str:token>/claim", pay.PublicPayLinkClaimView.as_view(), name="pay-link-claim"),
]
