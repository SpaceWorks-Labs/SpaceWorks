"""Pure core policy tests; runnable without Django or a database."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest
from uuid import uuid4

from apps.payments.event_payouts.ledger_math import (
    Entry, effective_paid, effective_tips, validate_append, validate_record_metadata,
)
from apps.payments.event_payouts.retention_policy import Closure, deletion_due, retain_closure
from apps.payments.event_payouts.validation import MAX_MINOR, PayoutValidationError, minor


class PayoutCalculations(unittest.TestCase):
    def setUp(self):
        self.obligation = uuid4()
        self.root = Entry(id=uuid4(), obligation_id=self.obligation, chain_uuid=uuid4(),
                          currency="INR", amount_minor=10000)

    def total(self, entries, approved=10000):
        return effective_paid(entries, obligation_id=self.obligation, currency="INR", approved_minor=approved)

    def test_correction_replaces_original_and_partial_payment_adds(self):
        correction = replace(self.root, id=uuid4(), amends_id=self.root.id, amount_minor=9000)
        partial = replace(self.root, id=uuid4(), chain_uuid=uuid4(), amount_minor=1000)
        self.assertEqual(self.total([self.root, correction]), 9000)
        self.assertEqual(self.total([self.root, correction, partial]), 10000)

    def test_void_preserves_history_and_reduces_only_its_chain(self):
        void = replace(self.root, id=uuid4(), amends_id=self.root.id, amount_minor=0, is_void=True)
        self.assertEqual(self.total([self.root, void]), 0)
        self.assertEqual(effective_tips([self.root, void]), (void,))

    def test_stale_tip_cannot_fork_even_when_amount_fits(self):
        first = replace(self.root, id=uuid4(), amends_id=self.root.id, amount_minor=9000)
        second = replace(first, id=uuid4(), amount_minor=8000)
        with self.assertRaisesRegex(PayoutValidationError, "payout_tip_changed"):
            validate_append([self.root, first], second, approved_minor=10000)

    def test_fork_in_loaded_history_is_refused(self):
        first = replace(self.root, id=uuid4(), amends_id=self.root.id, amount_minor=9000)
        with self.assertRaisesRegex(PayoutValidationError, "payout_chain_fork"):
            self.total([self.root, first, replace(first, id=uuid4())])

    def test_cross_obligation_or_currency_amendment_is_refused(self):
        for changes in ({"currency": "USD"}, {"obligation_id": uuid4()}, {"chain_uuid": uuid4()}):
            with self.subTest(changes=tuple(changes)):
                candidate = replace(self.root, id=uuid4(), amends_id=self.root.id, **changes)
                with self.assertRaises(PayoutValidationError):
                    self.total([self.root, candidate])

    def test_cycle_without_root_is_refused(self):
        second_id = uuid4()
        first = replace(self.root, amends_id=second_id)
        second = replace(self.root, id=second_id, amends_id=self.root.id)
        with self.assertRaisesRegex(PayoutValidationError, "payout_chain_cycle"):
            self.total([first, second])

    def test_dangling_parent_and_duplicate_ids_are_refused(self):
        for rows in ([replace(self.root, amends_id=uuid4())], [self.root, self.root]):
            with self.assertRaises(PayoutValidationError):
                self.total(rows)

    def test_multiple_roots_on_one_chain_are_refused(self):
        with self.assertRaisesRegex(PayoutValidationError, "duplicate_payout_chain"):
            self.total([self.root, replace(self.root, id=uuid4())])

    def test_new_partial_payment_cannot_exceed_approved(self):
        partial = replace(self.root, id=uuid4(), chain_uuid=uuid4(), amount_minor=1)
        with self.assertRaisesRegex(PayoutValidationError, "payout_exceeds_approval"):
            validate_append([self.root], partial, approved_minor=10000)

    def test_boolean_float_exponent_or_negative_amounts_are_refused(self):
        for value in (True, 1.0, "1e3", -1, MAX_MINOR + 1):
            with self.subTest(type=type(value).__name__), self.assertRaises(PayoutValidationError):
                minor(value)

    def test_zero_requires_explicit_void_amendment(self):
        for candidate in (replace(self.root, amount_minor=0), replace(self.root, amount_minor=0, is_void=True),
                          replace(self.root, amends_id=uuid4(), amount_minor=3, is_void=True)):
            with self.assertRaises(PayoutValidationError):
                self.total([candidate])

    def test_record_requires_aware_nonfuture_date_and_bounded_reference(self):
        now = datetime(2026, 10, 18, tzinfo=UTC)
        good = {"method": "bank_transfer", "payment_reference": "bank-ref-1", "paid_at": now, "now": now}
        self.assertEqual(validate_record_metadata(**good)["reference"], "bank-ref-1")
        for change in ({"method": "card_machine"}, {"paid_at": now + timedelta(seconds=1)},
                       {"paid_at": now.replace(tzinfo=None)}, {"payment_reference": " "},
                       {"payment_reference": "x" * 65}, {"payment_reference": "x\ny"}):
            with self.assertRaises(PayoutValidationError):
                validate_record_metadata(**{**good, **change})


class RetentionCalculations(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 18, tzinfo=UTC)
        self.closure = Closure(terminal_financial_at=self.at, reason_code="fully_paid", operation_id=uuid4(),
                               policy_revision=1, retention_days=2555)

    def test_receipt_uses_terminal_anchor_and_snapshotted_duration(self):
        self.assertEqual(self.closure.expires_at, self.at + timedelta(days=2555))
        self.assertFalse(deletion_due(now=self.closure.expires_at - timedelta(seconds=1), closure=self.closure,
                                      liability_open=False, hold_active=False))
        self.assertTrue(deletion_due(now=self.closure.expires_at, closure=self.closure,
                                     liability_open=False, hold_active=False))

    def test_unpaid_or_held_or_unclosed_evidence_never_expires(self):
        now = self.at + timedelta(days=3000)
        for change in ({"liability_open": True}, {"hold_active": True}, {"closure": None}):
            values = {"now": now, "closure": self.closure, "liability_open": False, "hold_active": False}
            self.assertFalse(deletion_due(**{**values, **change}))

    def test_purge_retry_preserves_anchor_and_rejects_clock_reset(self):
        self.assertIs(retain_closure(self.closure, self.closure), self.closure)
        with self.assertRaisesRegex(PayoutValidationError, "financial_closure_conflict"):
            retain_closure(self.closure, replace(self.closure, terminal_financial_at=self.at + timedelta(days=1)))

    def test_payee_uses_thirty_day_policy(self):
        self.assertEqual(replace(self.closure, retention_days=30).expires_at, self.at + timedelta(days=30))

    def test_invalid_policy_and_naive_dates_are_refused(self):
        for changes in ({"retention_days": True}, {"policy_revision": 0}, {"operation_id": "not-a-uuid"},
                        {"terminal_financial_at": self.at.replace(tzinfo=None)}):
            with self.assertRaises(PayoutValidationError):
                replace(self.closure, **changes)


if __name__ == "__main__":
    unittest.main()
