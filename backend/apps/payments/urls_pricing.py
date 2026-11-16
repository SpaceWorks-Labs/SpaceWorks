"""Lane L15 pricing routes: rate cards, item prices, discounts, loan charges and the quote.

Mounted with `apps.payments.urls`, unconditionally: pricing is ledger core (it decides
what is owed), never the removable online rail. Each view refuses while its capability
(`charges.pricing`, `charges.discounts`, `loans.fee_waivers`) is off.
"""

from django.urls import path

from apps.payments import views_loan_charges as loans
from apps.payments import views_pricing as rates
from apps.payments import views_pricing_discounts as discounts
from apps.payments import views_pricing_items as items
from apps.payments import views_pricing_quote as quote

SPACE = "admin/makerspace/<int:makerspace_id>"
LOAN = f"{SPACE}/requests/<int:request_id>"

PRICING_PATTERNS = [
    path(f"{SPACE}/pricing/currency", rates.PricingCurrencyView.as_view(), name="pricing-currency"),
    path(f"{SPACE}/pricing/loans/rental-timing", rates.RentalTimingView.as_view(), name="pricing-rental-timing"),
    path(f"{SPACE}/pricing/discounts", discounts.DiscountListView.as_view(), name="pricing-discounts"),
    path(f"{SPACE}/pricing/discounts/<int:discount_id>", discounts.DiscountDetailView.as_view(),
         name="pricing-discount"),
    path(f"{SPACE}/pricing/discounts/<int:discount_id>/archive", discounts.DiscountArchiveView.as_view(),
         name="pricing-discount-archive"),
    path(f"{SPACE}/pricing/overrides/<str:target_type>/<int:target_id>", items.PriceOverrideView.as_view(),
         name="pricing-override"),
    path(f"{SPACE}/pricing/<str:domain>", rates.PricingDefaultView.as_view(), name="pricing-default"),
    path(f"{SPACE}/pricing/<str:domain>/impact", rates.PricingImpactView.as_view(), name="pricing-impact"),
    path(f"{LOAN}/charges", loans.LoanChargesView.as_view(), name="loan-charges"),
    path(f"{LOAN}/fee-waivers", loans.LoanFeeWaiverView.as_view(), name="loan-fee-waivers"),
    path(f"{LOAN}/fee-waivers/<int:waiver_id>/revoke", loans.LoanFeeWaiverRevokeView.as_view(),
         name="loan-fee-waiver-revoke"),
    path(f"{LOAN}/accountability/<int:accountability_id>/charge", loans.AccountabilityChargeView.as_view(),
         name="loan-accountability-charge"),
    path("public/<slug:makerspace_slug>/pricing/quote", quote.PricingQuoteView.as_view(), name="pricing-quote"),
]
