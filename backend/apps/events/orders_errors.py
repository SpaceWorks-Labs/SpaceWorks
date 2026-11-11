"""Typed refusals for ticket orders, holds, claims, transfers and the refund override (L6).

Each carries a stable `code` the clients branch on: `sold_out`, `hold_expired`,
`access_code_invalid`, `order_limit`, `transfer_not_allowed`, `policy_less_generous`,
plus a few shape errors (`claim_invalid`, `claim_email_mismatch`, ...).
"""

from rest_framework.exceptions import APIException

STATUS = {
    "sold_out": 409, "hold_expired": 409, "order_limit": 400, "access_code_invalid": 404,
    "transfer_not_allowed": 409, "policy_less_generous": 409, "price_changed": 409,
    "claim_invalid": 404, "claim_email_mismatch": 403, "order_not_payable": 409,
    "amount_below_minimum": 400, "addon_unavailable": 409, "type_change_not_allowed": 409,
    "venue_fee_charged": 409, "nothing_to_collect": 409, "already_registered": 409,
    "online_payments_off": 409, "payment_rail_conflict": 409, "payment_settlement_pending": 409,
    "payments_unavailable": 503,
}


class OrderRefused(APIException):
    status_code = 409
    default_code = "order_refused"

    def __init__(self, code, detail, **extra):
        self.status_code = STATUS.get(code, 409)
        super().__init__({"detail": detail, "code": code, **extra})
        self.code = code
