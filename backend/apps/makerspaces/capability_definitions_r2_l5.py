"""Release-2 lane L5: money, tax, documents and the space's finance ledger (#71, #94, #100).

All seven keys are parentless, like `billing.documents` and `charges.enabled`: money
tracking is core and never depends on the removable `payments` rail (Hard Rule). Each
switch keeps its data when turned off (#95, #128 C-8):

* `billing.tax` -- the tax engine (single named tax or India GST), FY document series and
  the GST return reports. Off: every charge and document is exactly release 1.
* `billing.maker_checker` -- a second person with record_payment confirms every offline
  settlement of a charge (#128 C-5: offline INCOME only, never spending).
* `billing.offline_claims` -- the UPI QR for the exact amount and the payer's "I've paid"
  claim that staff confirm or reject.
* `billing.pay_links` -- signed, expiring pay links for account-less charges staff raised.
* `billing.disputes` -- the disputes list and staff notice. Provider disputes are always
  RECORDED (money facts); the switch only shows or hides them.
* `billing.capture_flags` -- late, duplicate and mismatched online captures are flagged and
  their receipt held for a staff decision. Off: release-1 behaviour (receipt on capture).
* `finance.ledger` -- the finance ledger screens and reports. Spending is ALWAYS recorded
  (#128 C-15); this switch hides only the UI and reports.
"""


def definitions(feature):
    return (
        feature(
            "billing.tax", None, "Tax on charges",
            "Charge a single named tax or India GST (CGST/SGST/IGST), number tax invoices per "
            "financial year and file GSTR-1 and GSTR-3B from the reports.",
        ),
        feature(
            "billing.maker_checker", None, "Two-person check for offline income",
            "A second person with record-payment authority confirms every cash, UPI or bank "
            "settlement before the charge is marked paid. Never applies to spending.",
        ),
        feature(
            "billing.offline_claims", None, "UPI QR and \"I've paid\" claims",
            "Show a UPI QR for the exact amount and let payers tell you they paid; staff confirm "
            "or reject each claim.",
        ),
        feature(
            "billing.pay_links", None, "Pay links for people without an account",
            "Send a signed, expiring link that pays exactly one charge staff raised.",
        ),
        feature(
            "billing.disputes", None, "Payment disputes",
            "List chargebacks reported by Stripe or Razorpay. A record only: nothing is cancelled "
            "or refunded automatically.",
            default_enabled=True,
        ),
        feature(
            "billing.capture_flags", None, "Unexpected online payments",
            "Flag money that arrives late, twice or for a different amount, and hold its receipt "
            "until staff decide.",
            default_enabled=True,
        ),
        feature(
            "finance.ledger", None, "Finance ledger",
            "Income against spending by month and area, expenses, opening balances and the "
            "per-event money view. Spending is always recorded; this shows the screens.",
            default_enabled=True,
        ),
    )
