"""Execute production validation against G1's literal closed evidence, no ORM."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from uuid import UUID, uuid4

from apps.payments.event_payouts.decision_snapshots import validate_summary
from apps.payments.event_payouts.validation import PayoutValidationError
from apps.payments.event_payouts.wire import cancellation_command, command_digest, utc

C = json.loads((Path(__file__).resolve().parents[2] / "events/programme/contracts/reimbursement_addon.json").read_text(encoding="utf8"))


class ClosedDecisionEvidence(unittest.TestCase):
    def setUp(self):
        self.value = deepcopy(C["core_evidence"]["decision_summary"])

    def reject(self, mutate):
        mutate(self.value)
        with self.assertRaises(PayoutValidationError):
            validate_summary(self.value)

    def test_frozen_snapshot_executes_and_result_cannot_modify_input(self):
        result = validate_summary(self.value)
        self.assertEqual(result, C["core_evidence"]["decision_summary"])
        result["decision"]["reason"] = "Changed"
        self.assertNotEqual(result, self.value)

    def test_unknown_bank_data_rejected_at_every_object_level(self):
        for path in ((), ("source",), ("decision",), ("award",), ("totals",), ("eligibility",),
                     ("award", "applied_rules"), ("lines", 0), ("lines", 0, "receipt"), ("lines", 0, "limits")):
            self.setUp()
            row = self.value
            for key in path:
                row = row[key]
            self.reject(lambda _: row.update(bank_account="FORBIDDEN"))

    def test_missing_every_required_field_fails_closed(self):
        for field in tuple(self.value):
            self.setUp()
            self.reject(lambda value: value.pop(field))

    def test_bool_float_negative_and_overflow_money_refused(self):
        for bad in (True, 1.0, -1, "150000", 9_000_000_000_000_001):
            self.setUp()
            self.reject(lambda value: value["totals"].update(approved_minor=bad))

    def test_line_and_total_arithmetic_cannot_be_fabricated(self):
        for mutate in (
            lambda v: v["lines"][0].update(converted_minor=174999),
            lambda v: v["totals"].update(claimed_minor=174999),
            lambda v: v["totals"].update(approved_minor=149999),
            lambda v: v["award"].update(cap_minor=149999),
            lambda v: v["award"]["applied_rules"]["category_caps"].update(rail=149999),
            lambda v: v["lines"][0]["limits"].update(cap_minor=149999),
            lambda v: v["lines"][0].update(fx_rate="1.1"),
            lambda v: v["lines"][0].update(original_exponent=0),
            lambda v: v["lines"][0].update(target_exponent=3),
            lambda v: v["lines"][0].update(currency="USD"),
            lambda v: v["lines"][0].update(rounding="HALF_EVEN"),
        ):
            self.setUp()
            self.reject(mutate)

    def test_duplicate_lines_receipt_overallocation_and_missing_override_rejected(self):
        self.reject(lambda v: v["lines"].append(deepcopy(v["lines"][0])))
        self.setUp()
        self.reject(lambda v: v["lines"][0]["receipt"].update(total_minor=174999))
        self.setUp()
        self.reject(lambda v: v["lines"][0]["receipt"].update(override_uuid=str(uuid4())))

    def test_cap_or_category_reduction_is_partial_relative_to_requested_amount(self):
        self.reject(lambda v: v["decision"].update(outcome="approved"))
        self.setUp()
        self.value["award"]["cap_minor"] = self.value["award"]["applied_rules"]["category_caps"]["rail"] = 175000
        self.value["lines"][0]["limits"]["cap_minor"] = 175000
        self.value["lines"][0]["approved_minor"] = self.value["totals"]["approved_minor"] = 175000
        self.reject(lambda v: None)
        self.value["decision"]["outcome"] = "approved"
        validate_summary(self.value)

    def test_invalid_uuid_date_currency_and_arbitrary_eligibility_reference_rejected(self):
        for mutate in (lambda v: v["source"].update(claim_uuid="bad"),
                       lambda v: v["decision"].update(decided_at="2026-12-05T10:00:00"),
                       lambda v: v["lines"][0].update(expense_date="2026-13-01"),
                       lambda v: v["award"].update(currency="MGA"),
                       lambda v: v["eligibility"].update(project_snapshot_ref="https://private.invalid")):
            self.setUp()
            self.reject(mutate)


class CanonicalCommands(unittest.TestCase):
    def test_frozen_cancellation_digest_is_body_only(self):
        data = deepcopy(C["core_evidence"]["cancellation_command"])
        self.assertEqual(command_digest("obligation.cancel", uuid4(), data),
                         C["core_evidence"]["cancellation_revision"]["command_digest"])
        data["operation_id"] = UUID(data["operation_id"])
        self.assertEqual(command_digest("obligation.cancel", uuid4(), data),
                         C["core_evidence"]["cancellation_revision"]["command_digest"])

    def test_changed_payload_changes_durable_digest(self):
        data = deepcopy(C["core_evidence"]["cancellation_command"])
        original = command_digest("obligation.cancel", uuid4(), data)
        for key, value in (("note", "Other reason"), ("expected_version", 5), ("expected_pool_version", 3)):
            self.assertNotEqual(original, command_digest("obligation.cancel", uuid4(), {**data, key: value}))
        with self.assertRaises(PayoutValidationError):
            cancellation_command({**data, "bank_account": "no"})

    def test_normalization_and_canonical_utc_match_frozen_encoding(self):
        command = deepcopy(C["core_evidence"]["cancellation_command"])
        padded = {**command, "note": "  " + command["note"] + "  "}
        self.assertEqual(cancellation_command(padded), command)
        instant = datetime(2026, 12, 1, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(utc(instant), C["rsvp_identity"]["instant"])
        self.assertEqual(utc(instant.replace(microsecond=1000)), "2026-12-01T10:00:00.001000Z")
        with self.assertRaises(PayoutValidationError):
            utc(instant.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
