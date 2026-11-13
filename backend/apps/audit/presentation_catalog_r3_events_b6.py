"""Audit presentation for parity E-B6: refund-driven ticket cancellation and staff expense claims.

Labels only. The ticket rows carry a case, a payment and a count; the claim row carries a request id and a flag.
No amount, name or note is reachable through the metadata path.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("payment.refund_case_tickets_cancelled", gettext_noop("Tickets cancelled with an approved refund")),
    P("payment.refund_case_tickets_cancel_failed", gettext_noop("Cancelling tickets after an approved refund failed")),
    P("event.reimbursement.staff_claim_filed", gettext_noop("Staff expense claim filed")),
)
