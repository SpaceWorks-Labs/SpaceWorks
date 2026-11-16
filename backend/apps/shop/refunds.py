"""Shop money goes back ONLY through a staff-approved refund case in area `shop` (#59, Q-S7).

Returns, uncollected and unfilled orders open (or grow) the order charge's case; deciding it
is the ordinary refund-case queue. The direct staff refund routes refuse shop orders
(`refund_via_case_only`), so no sale is refunded without that decision. Lane L18 has the
same guard for gifts (`payments.donations.refunds`); the two subject lists join at merge.
"""

from django.utils.translation import gettext
from apps.payments.exceptions_refunds import RefundNotAllowed

CASE_ONLY_SUBJECTS = ("shop_order",)


def refuse_direct_refund(payment):
    if payment is not None and payment.subject_type in CASE_ONLY_SUBJECTS:
        raise RefundNotAllowed(gettext("Shop sales are refunded through a refund case that staff approve."),
                               "refund_via_case_only")
