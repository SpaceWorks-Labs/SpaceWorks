"""Direct stdlib execution reconciles R's actual helpers to the G1 fixture."""
from datetime import UTC, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.events.staged_forms.command_values import canonical_utc, form_intent_status, rsvp_identity
from apps.events.staged_forms.portable import remap_json, import_values
from apps.events.staged_forms.object_capture import disposition
from apps.events.contracts.form_operations import child_form_operation_id
from types import SimpleNamespace

C = json.loads((Path(__file__).parents[1] / "programme/contracts/reimbursement_addon.json").read_text(encoding="utf-8"))


class ContractValues(unittest.TestCase):
    def test_utc_identity_matches_frozen_encoding_and_equivalent_offsets(self):
        value = C["rsvp_identity"]
        instant = datetime.fromisoformat(value["instant"])
        for due in (instant, instant.astimezone(timezone(timedelta(hours=5, minutes=30)))):
            row = SimpleNamespace(pk=81, decision_revision=3, rsvp_due_at=due)
            self.assertEqual(rsvp_identity(row), value["example"])
        self.assertEqual(canonical_utc(instant.replace(microsecond=123)), "2026-12-01T10:00:00.000123Z")
        with self.assertRaises(ValueError):
            canonical_utc(instant.replace(tzinfo=None))

    def test_child_and_per_form_status_vectors_are_literal(self):
        inline = C["inline_forms"]
        for status in inline["statuses"] + [inline["no_save"]]:
            child = child_form_operation_id(UUID(inline["outer_operation_id"]), event_id=inline["event_id"],
                owner_id=inline["owner_id"], slot=status["slot"])
            self.assertEqual(str(child), status["operation_id"])
            self.assertEqual(form_intent_status(slot=status["slot"], operation_id=child, intent_id=status["intent_id"]), status)

    def test_portable_reference_mapping_never_rewrites_user_text(self):
        raw = {"answers": [{"id": "text", "type": "short_text", "value": "asset_id:91"},
            {"id": "upload", "type": "file", "value": [C["legacy"]["FILE_REF"]]}]}
        result = remap_json("events.StageFormResponseRevision.answers_snapshot", raw, map_id=lambda label, pk: pk + 1000)
        self.assertEqual(result["answers"][0], raw["answers"][0])
        self.assertEqual(result["answers"][1]["value"][0]["asset_id"], 1091)
        self.assertEqual(raw["answers"][1]["value"][0]["asset_id"], 91)
        with self.assertRaises(ValueError):
            remap_json("arbitrary", raw, map_id=lambda label, pk: pk)

    def test_import_pauses_assignments_and_never_restarts_expiry(self):
        self.assertIsNone(import_values("events.StageActivationJob", {}, fidelity="PORTABLE"))
        value = import_values("events.StageFormAssignment", {"creation_operation_id": "old", "registration_id": 1}, fidelity="PORTABLE")
        self.assertTrue(value["imported_paused"])
        self.assertIsNone(value["creation_operation_id"])
        at = datetime(2026, 12, 1, tzinfo=UTC)
        row = SimpleNamespace(state="attached", expired_at=None, expires_at=at)
        self.assertEqual(disposition(row, now=at), "retention_finalization_required")
        row.expired_at, row.state = at, "expired"
        self.assertEqual(disposition(row, now=at), "expected_expired")


if __name__ == "__main__":
    unittest.main()
