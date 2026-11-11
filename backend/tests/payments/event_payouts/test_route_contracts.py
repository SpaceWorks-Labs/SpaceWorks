"""G1 literal URL/method contracts and core dependency boundaries, model-free."""
import ast
import json
from pathlib import Path
import re
import unittest

BACKEND = Path(__file__).resolve().parents[3]
PACKAGE = BACKEND / "apps/payments/event_payouts"
C = json.loads((BACKEND / "tests/events/programme/contracts/reimbursement_addon.json").read_text())


class CoreSurfaceContracts(unittest.TestCase):
    def test_every_frozen_core_route_has_exact_path_and_methods(self):
        actual = {}
        for module, prefix in (("urls_finance", "/api/v1/admin/makerspaces/{makerspace_id}/event-payouts/"),
                               ("urls_member", "/api/v1/member/event-payouts/")):
            tree = ast.parse((PACKAGE / (module + ".py")).read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "path":
                    continue
                suffix = ast.literal_eval(node.args[0])
                name = next(ast.literal_eval(kw.value) for kw in node.keywords if kw.arg == "name")
                actual[name] = prefix + re.sub(r"<(?:uuid|int):([a-z_]+)>", r"{\1}", suffix)
        frozen = {row["name"]: row for row in C["routes"] if "/event-payouts" in row["path"]}
        self.assertEqual(set(actual), set(frozen))
        for name, path in actual.items():
            with self.subTest(route=name):
                self.assertEqual(path, frozen[name]["path"])
        self.assertNotIn("member-event-receipt-file-download", actual)

    def test_core_never_imports_removable_events_or_reimbursement_runtime(self):
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                self.assertFalse(any(name.startswith(("apps.event_reimbursements", "apps.events")) for name in names), str(path))

    def test_snapshot_openapi_fields_match_frozen_closed_schema(self):
        tree = ast.parse((PACKAGE / "serializers_snapshot.py").read_text())
        classes = {node.name: {child.targets[0].id for child in node.body if isinstance(child, ast.Assign)
            and isinstance(child.targets[0], ast.Name)} for node in tree.body if isinstance(node, ast.ClassDef)}
        schema = C["schemas"]["decision_summary"]
        self.assertEqual(classes["DecisionSummarySerializer"], set(schema["required"]))
        for name, key in (("Source", "source"), ("Decision", "decision"), ("Award", "award"), ("Totals", "totals")):
            self.assertEqual(classes[name], set(schema["properties"][key]["required"]))
        for name, key in (("Receipt", "receipt"), ("DecisionLine", "decision_line"), ("EligibilityEvidence", "eligibility")):
            self.assertEqual(classes[name], set(schema["$defs"][key]["required"]))


if __name__ == "__main__":
    unittest.main()
