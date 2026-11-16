"""One row's renewal answer for a member-facing list: `(can_renew, refusal_code)`.

Wraps `renewal_workflow.check_renewal`, the same read-only check the member activity
endpoint and the locked renewal mutation use, so a list can never offer a renewal the
mutation would refuse. Works for account-only borrowers (membership off) because that
rule lives inside `check_renewal` (`self_renewal_allowed`, decision 221a).
"""

from rest_framework.exceptions import ValidationError

from apps.makerspaces.loan_policy import renewal_cap
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from apps.makerspaces.platform import feature_enabled

from .renewal_workflow import ACTIVE_LOAN_STATUSES, check_renewal


class RenewalStateResolver:
    """Resolves the policy and the `loans.renewals` switch once per space, then each row."""

    def __init__(self, makerspace, member):
        self.member = member
        self.policy = MakerspaceLoanPolicy.for_makerspace(makerspace)
        self.enabled = feature_enabled(makerspace, "loans.renewals")

    def state(self, loan):
        if loan.status not in ACTIVE_LOAN_STATUSES:
            return False, "loan_not_active"
        if not self.enabled:
            return False, "renewals_off"
        try:
            check_renewal(loan, self.policy, actor=self.member)
        except ValidationError as exc:
            detail = exc.detail
            return False, str(detail["code"]) if isinstance(detail, dict) and "code" in detail else "renewal_refused"
        return True, None

    def renewals_left(self, loan):
        """Renewals this loan may still take under the policy cap (#234), or None when renewals are off.

        Uses the prefetched items (outstanding ones only) and the same ``renewal_cap`` the
        mutation checks; other refusals (a waiting borrower, a lapsed term) stay in ``state``.
        """
        if (not self.enabled or loan.status not in ACTIVE_LOAN_STATUSES
                or self.policy.loan_renewal_mode != MakerspaceLoanPolicy.RenewalMode.AUTO):
            return None
        products = [item.product for item in loan.items.all()
                    if item.issued_quantity > item.returned_quantity + item.damaged_quantity + item.missing_quantity]
        return max(0, renewal_cap(self.policy, products) - loan.renewal_count)
