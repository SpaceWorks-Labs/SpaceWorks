"""The frozen literal method inventory is an integration boundary, not a mock API."""
import json
from pathlib import Path
import unittest

BACKEND = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((BACKEND / "apps/event_reimbursements/manifest.json").read_text())
CONTRACT = json.loads((BACKEND / "tests/events/programme/contracts/reimbursement_addon.json").read_text())


class ManifestContract(unittest.TestCase):
    def test_every_owned_frozen_name_has_exact_methods(self):
        actual = {row["name"]: row for row in MANIFEST["routes"]}
        wanted = {row["name"]: row for row in CONTRACT["routes"] if
            row["name"].startswith(("member-event-reimbursement", "admin-event-reimbursement", "member-event-receipt-file"))}
        self.assertEqual(set(actual), set(wanted))
        for name in wanted:
            self.assertEqual(set(actual[name]["methods"]), set(wanted[name]["methods"]), name)
        self.assertNotIn("member-event-receipt-file-download", actual)

    def test_manifest_keeps_money_and_bytes_in_core(self):
        self.assertEqual(MANIFEST["object_fields"]["owned"], [])
        self.assertEqual(len(MANIFEST["models"]), 16)
        self.assertTrue(all(row["label"].startswith("event_reimbursements.") for row in MANIFEST["models"]))
        self.assertTrue(all(row["live_host"] for row in MANIFEST["routes"]))


if __name__ == "__main__":
    unittest.main()
