"""Executable typed-reference/fidelity tests requiring only Python's stdlib."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from apps.event_reimbursements.portable import transform, remap_structured


class PortableContracts(unittest.TestCase):
    def project(self, label, fields, fidelity="full"):
        return transform(label="event_reimbursements." + label, fields=fields, fidelity=fidelity,
            map_reference=lambda label, value: int(value) + 100 if isinstance(value, (int, str)) and str(value).isdigit() else "mapped:" + str(value),
            transform_pii=lambda **kw: "target-envelope:" + kw["remap"](kw["source_value"]), target_now="2030-01-01T00:00:00Z")

    def test_programme_pauses_without_releasing_or_changing_budget(self):
        result = self.project("ReimbursementProgramme", {"enabled": True, "request_opens_at": "old", "currency": "INR"})
        self.assertFalse(result["enabled"])
        self.assertTrue(result["imported_paused"])
        self.assertEqual(result["currency"], "INR")
        self.assertEqual(result["request_closes_at"], "2030-01-01T00:00:00Z")

    def test_pool_counters_are_exactly_preserved(self):
        fields = {"total_minor": 10000, "reserved_minor": 3000, "committed_minor": 5000, "currency": "KWD"}
        self.assertEqual(self.project("ReimbursementBudgetPool", fields), fields)

    def test_draft_receipt_references_are_remapped_inside_custody(self):
        value = self.project("ReimbursementClaim", {"draft_payload": json.dumps({"lines": [
            {"receipt": {"asset_id": 91, "sha256": "a" * 64, "generation": 2}}]})})
        decoded = json.loads(value["draft_payload"].removeprefix("target-envelope:"))
        self.assertEqual(decoded["lines"][0]["receipt"]["asset_id"], 191)
        self.assertEqual(decoded["lines"][0]["receipt"]["generation"], 2)

    def test_fixed_form_id_maps_programme_not_generic_embedded_numbers(self):
        value = self.project("GrantRequest", {"estimated_cost": json.dumps({"form": {"form_id": "reimbursement-request-9"},
            "snapshot": {"form_id": "reimbursement-request-9"}, "amount_minor": 9})})
        decoded = json.loads(value["estimated_cost"].removeprefix("target-envelope:"))
        self.assertEqual(decoded["form"]["form_id"], "reimbursement-request-109")
        self.assertEqual(decoded["snapshot"]["form_id"], "reimbursement-request-109")
        self.assertEqual(decoded["amount_minor"], 9)

    def test_redacted_claim_drops_identifying_text_but_preserves_money(self):
        fields = {"vendor": "person", "traveller": "name", "route": "{}", "original_amount_minor": 501, "converted_minor": 600}
        result = self.project("ClaimLine", fields, "redacted")
        self.assertEqual((result["vendor"], result["traveller"], result["route"]), ("", "", "{}"))
        self.assertEqual((result["original_amount_minor"], result["converted_minor"]), (501, 600))

    def test_only_coordination_work_is_dropped(self):
        self.assertIsNone(self.project("ReimbursementWorkItem", {"state": "pending"}))
        self.assertEqual(self.project("BudgetEntry", {"operation_id": "durable", "amount_minor": -100}),
                         {"operation_id": "durable", "amount_minor": -100})

    def test_cancellation_evidence_pointer_and_decision_provenance_remap(self):
        value = self.project("ClaimAppeal", {"resolved_by_cancellation_revision_id": 23, "statement": "Private"})
        self.assertEqual(value["resolved_by_cancellation_revision_id"], 123)
        self.assertTrue(value["statement"].startswith("target-envelope:"))

    def test_transform_does_not_mutate_source(self):
        source = {"enabled": True, "tier_rules": {"tier": {"amount_minor": 10}}}
        self.project("ReimbursementProgramme", source)
        self.assertTrue(source["enabled"])

    def test_unknown_fidelity_or_foreign_label_refuses(self):
        for label, fidelity in (("payments.Payment", "full"), ("event_reimbursements.ClaimLine", "plain")):
            with self.assertRaises(ValueError):
                transform(label=label, fields={}, map_reference=lambda *a: None, fidelity=fidelity,
                          transform_pii=lambda **kw: None, target_now=None)


if __name__ == "__main__":
    unittest.main()
