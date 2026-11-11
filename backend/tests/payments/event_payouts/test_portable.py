"""Pure custodial transforms preserve financial meaning and exclude payee values."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import unittest
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5
from apps.payments.event_payouts.portable import (remap_summary, remap_eligibility, remap_hold_refs,
    import_attachment, import_obligation, import_payee, money_fingerprint, EPHEMERAL_MODELS)
from apps.payments.event_payouts.preflight import Facts

C = json.loads((Path(__file__).resolve().parents[2] / "events/programme/contracts/reimbursement_addon.json").read_text())


class CustodialFinance(unittest.TestCase):
    def test_typed_remap_changes_only_declared_identity_references(self):
        value = C["core_evidence"]["decision_summary"]
        calls = []
        def mapper(label, identifier):
            calls.append((label, identifier))
            return identifier + 1000
        result = remap_summary(value, map_id=mapper, map_uuid=lambda label, value: value)
        self.assertEqual(result["decision"]["actor_id"], 1005)
        self.assertEqual(result["lines"][0]["receipt"]["attachment_id"], 1091)
        self.assertEqual(result["totals"], value["totals"])
        self.assertEqual(result["source"], value["source"])
        self.assertEqual(result["lines"][0]["vendor"], "Rail vendor")
        self.assertIn(("events.EventCheckInEvent", 34), calls)

    def test_redacted_fidelity_preserves_arithmetic_codes_and_closed_schema(self):
        value = C["core_evidence"]["decision_summary"]
        result = remap_summary(value, map_id=lambda label, identifier: identifier,
            map_uuid=lambda label, value: value, fidelity="redacted")
        self.assertEqual(result["totals"], value["totals"])
        self.assertEqual(result["lines"][0]["reason_code"], "policy_cap")
        self.assertEqual(result["lines"][0]["vendor"], "[redacted]")
        self.assertNotIn("A Maker", json.dumps(result))
        self.assertNotIn("Bounded to", json.dumps(result))

    def test_restore_applies_current_payee_expiry_without_resetting_policy(self):
        now = datetime(2026, 10, 18, tzinfo=UTC)
        value = {"state": "current", "details": "private", "purge_due_at": now - timedelta(days=1)}
        result = import_payee(value, now=now, hold_active=False, liability_open=False)
        self.assertEqual((result["state"], result["details"]), ("purged", ""))
        self.assertEqual(import_payee(value, now=now, hold_active=True, liability_open=False)["details"], "private")
        self.assertEqual(import_payee(value, now=now, hold_active=False, liability_open=True)["details"], "private")

    def test_money_drift_or_settlement_vetoes_stale_publication(self):
        row = {"id": uuid4(), "currency": "INR", "approved_minor": 150000, "state": "open", "current_revision_id": 1}
        first = money_fingerprint([row], [])
        self.assertNotEqual(first, money_fingerprint([{**row, "approved_minor": 149999}], []))
        entry = {"id": uuid4(), "obligation_id": row["id"], "currency": "INR", "amount_minor": 1,
                 "amends_id": None, "is_void": False}
        self.assertNotEqual(first, money_fingerprint([row], [entry]))
        self.assertIn("payments.FinanceObjectCleanup", EPHEMERAL_MODELS)

    def test_eligibility_requires_canonical_flags_not_cached_status(self):
        evidence = C["core_evidence"]["decision_summary"]["eligibility"]
        facts = Facts(evidence, True, True, True, True, True)
        self.assertTrue(facts.eligible)
        self.assertEqual(Facts.from_dict(facts.as_dict()), facts)
        for key in ("participation_eligible", "attendance_eligible", "project_eligible", "event_active", "owner_active"):
            self.assertFalse(Facts.from_dict({**facts.as_dict(), key: False}).eligible)

    def test_uuid_mapping_is_explicit_stable_and_keeps_line_provenance_consistent(self):
        value = C["core_evidence"]["decision_summary"]
        def mapper(label, value):
            return uuid5(NAMESPACE_URL, label + ":" + value)
        result = remap_summary(value, map_id=lambda label, value: value, map_uuid=mapper)
        self.assertNotEqual(result["source"]["claim_uuid"], value["source"]["claim_uuid"])
        self.assertNotEqual(result["lines"][0]["line_uuid"], value["lines"][0]["line_uuid"])
        self.assertEqual(result["source"]["claim_uuid"], str(mapper("event_reimbursements.ReimbursementClaim.uuid", value["source"]["claim_uuid"])))
        self.assertEqual(result["totals"], value["totals"])

    def test_core_fact_and_hold_reference_maps_are_typed(self):
        evidence = C["core_evidence"]["decision_summary"]["eligibility"]
        facts = Facts(evidence, True, True, True, True, True, retained_only=True)
        result = remap_eligibility(facts.as_dict(), map_id=lambda label, value: value + 100,
            map_uuid=lambda label, value: value)
        self.assertEqual(result["evidence"]["registration_id"], 201)
        self.assertTrue(result["retained_only"])
        seen = []
        self.assertEqual(remap_hold_refs([7], map_id=lambda label, value: seen.append(label) or value + 1), [8])
        self.assertEqual(seen, ["payments.PayoutEligibility"])

    def test_import_keeps_attached_budget_coordination_only_with_proven_domain_closure(self):
        values = {"state": "open", "event_id": 41, "domain_coordination_state": "attached", "eligibility_status": "eligible"}
        with self.assertRaises(ValueError):
            import_obligation(values, domain_included=True, source_closure_proven=False)
        attached = import_obligation(values, domain_included=True, source_closure_proven=True)
        self.assertEqual(attached["domain_coordination_state"], "attached")
        self.assertEqual(attached["eligibility_status"], "needs_acknowledgement")
        detached = import_obligation(values, domain_included=False, source_closure_proven=True)
        self.assertEqual((detached["domain_coordination_state"], detached["event_id"]), ("detached", None))
        self.assertIsNone(import_attachment({"state": "validating"}))


if __name__ == "__main__":
    unittest.main()
