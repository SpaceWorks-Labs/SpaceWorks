"""Integer-only accounting examples independent of Django infrastructure."""

import unittest
from apps.event_reimbursements.budget_math import Balance, cancel_commitment, settle_reservation
from apps.event_reimbursements.calculations import convert_minor, percentage_cap
from apps.payments.event_payouts.validation import PayoutValidationError


class BudgetCalculations(unittest.TestCase):
    def test_offer_holds_funds_and_partial_approval_releases_unused_amount(self):
        balance = Balance(total_minor=10000).change(reserved=8000)
        self.assertEqual(balance.available_minor, 2000)
        decided = settle_reservation(balance, held_minor=8000, approved_minor=5000)
        self.assertEqual((decided.available_minor, decided.reserved_minor, decided.committed_minor), (5000, 0, 5000))

    def test_commitment_remains_consumed_after_settlement(self):
        balance = settle_reservation(Balance(total_minor=8000, reserved_minor=8000), held_minor=8000, approved_minor=8000)
        self.assertEqual(balance.available_minor, 0)

    def test_final_balance_cannot_be_reserved_twice(self):
        balance = Balance(total_minor=10000).change(reserved=10000)
        with self.assertRaisesRegex(PayoutValidationError, "budget_exhausted"):
            balance.change(reserved=1)

    def test_budget_withdrawal_cannot_reduce_existing_liability(self):
        with self.assertRaises(PayoutValidationError):
            Balance(total_minor=10000, reserved_minor=3000, committed_minor=5000).change(total=-2001)

    def test_rejection_releases_the_whole_hold(self):
        balance = settle_reservation(Balance(total_minor=5000, reserved_minor=5000), held_minor=5000, approved_minor=0)
        self.assertEqual(balance.available_minor, 5000)

    def test_cancel_releases_commitment_and_appeal_hold_once(self):
        balance = Balance(total_minor=10000, reserved_minor=3000, committed_minor=5000)
        cancelled = cancel_commitment(balance, committed_minor=5000, held_minor=3000)
        self.assertEqual(cancelled.available_minor, 10000)
        with self.assertRaises(PayoutValidationError):
            cancel_commitment(cancelled, committed_minor=5000, held_minor=3000)

    def test_appeal_reacquires_available_funds_or_refuses(self):
        balance = Balance(total_minor=10000, committed_minor=5000)
        self.assertEqual(balance.change(reserved=5000).available_minor, 0)
        with self.assertRaisesRegex(PayoutValidationError, "budget_exhausted"):
            balance.change(reserved=5001)

    def test_invalid_approvals_and_coercible_values_are_refused(self):
        for amount in (True, 1.0, "10", -1, 5001):
            with self.assertRaises(PayoutValidationError):
                settle_reservation(Balance(total_minor=5000, reserved_minor=5000), held_minor=5000, approved_minor=amount)


class CurrencyCalculations(unittest.TestCase):
    def test_jpy_to_inr_rounds_half_up_in_target_minor_units(self):
        self.assertEqual(convert_minor(original_minor=1, rate="0.005", source_exponent=0, target_exponent=2), 1)

    def test_kwd_to_jpy_and_inr_preserves_source_exponent(self):
        self.assertEqual(convert_minor(original_minor=1000, rate="500", source_exponent=3, target_exponent=0), 500)
        self.assertEqual(convert_minor(original_minor=1000, rate="250", source_exponent=3, target_exponent=2), 25000)

    def test_foreign_rate_is_major_ratio_and_rounded_once(self):
        self.assertEqual(convert_minor(original_minor=12345, rate="0.012345678912", source_exponent=2, target_exponent=3), 1524)

    def test_fx_rate_refuses_floats_exponent_strings_negative_and_excess_precision(self):
        for rate in (0.5, "1e3", "NaN", "Infinity", "-1", "0", "1.1234567890123", "1000000000000"):
            with self.assertRaises(PayoutValidationError):
                convert_minor(original_minor=1, rate=rate, source_exponent=2, target_exponent=2)

    def test_percentage_uses_basis_points_and_half_up_then_cap(self):
        self.assertEqual(percentage_cap(estimate_minor=1, basis_points=5000, cap_minor=100), 1)
        self.assertEqual(percentage_cap(estimate_minor=10001, basis_points=5000, cap_minor=4000), 4000)

    def test_boolean_or_out_of_range_basis_points_refused(self):
        for bps in (True, 0.5, -1, 10001):
            with self.assertRaises(PayoutValidationError):
                percentage_cap(estimate_minor=1000, basis_points=bps, cap_minor=1000)


if __name__ == "__main__":
    unittest.main()
