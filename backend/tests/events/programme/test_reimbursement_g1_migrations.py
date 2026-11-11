"""Static graph/inventory checks runnable without Django or a shared database."""
import ast
from collections import defaultdict
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))
from apps.encryption.registry import fields_for_label
from apps.makerspaces.module_registry import BY_KEY
from apps.makerspaces.role_catalog import ROLE_BY_SLUG

# The lane's own migrations, as numbered after landing on the events programme (g2) leaves.
NEW = {
    "events": (52, 57), "payments": (26, 30), "event_reimbursements": (1, 5),
    "encryption": (10, 11), "accounts": (44, 44), "makerspaces": (106, 107),
}
# Staging renumbered the lane onto the merged leaves; the programme's own 0052/0053 and
# saved-details 0044 share those numbers but are not reimbursement-lane migrations.
NOT_LANE = {("events", "0052_programme_field_state"), ("events", "0053_programme_guard_fixes"),
            ("accounts", "0044_saved_details_pk_state")}


def migration_nodes():
    result = {}
    for app in (BACKEND / "apps").iterdir():
        for path in (app / "migrations").glob("[0-9]*.py"):
            result[(app.name, path.stem)] = (path, ast.parse(path.read_text(encoding="utf8")))
    return result


def dependencies(tree):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Migration")
    node = next(n.value for n in cls.body if isinstance(n, ast.Assign) and n.targets[0].id == "dependencies")
    # Baseline swappable dependencies are expressions; new migrations are literal.
    return [tuple(ast.literal_eval(n)) for n in node.elts if isinstance(n, ast.Tuple)]


def new_nodes():
    return {key: pair for key, pair in migration_nodes().items() if key[0] in NEW
            and NEW[key[0]][0] <= int(key[1][:4]) <= NEW[key[0]][1] and key not in NOT_LANE}


class G1MigrationGraph(unittest.TestCase):
    def test_dependencies_exist_are_acyclic_and_have_one_leaf_per_changed_app(self):
        nodes = migration_nodes()
        visiting, done = set(), set()
        def visit(key):
            if key[0] in {"auth", "contenttypes", "admin", "sessions", "token_blacklist"}:
                return  # Installed Django packages are checked by MigrationLoader in the backend harness.
            self.assertTrue(key in nodes, f"missing repository migration: {key}")
            if key in done:
                return
            self.assertNotIn(key, visiting, f"migration cycle: {key}")
            visiting.add(key)
            for dep in dependencies(nodes[key][1]):
                visit(dep)
            visiting.remove(key)
            done.add(key)
        for key in new_nodes():
            visit(key)
        for app in NEW:
            keys = {key for key in nodes if key[0] == app}
            parents = {d for key in keys for d in dependencies(nodes[key][1]) if d[0] == app}
            self.assertEqual(len(keys - parents), 1, app)

    def test_core_has_no_reimbursement_dependency_or_fk(self):
        nodes = migration_nodes()
        def visit(key, seen):
            if key in seen:
                return
            if key[0] in {"auth", "contenttypes", "admin", "sessions", "token_blacklist"}:
                return
            seen.add(key)
            self.assertNotEqual(key[0], "event_reimbursements")
            for dep in dependencies(nodes[key][1]):
                visit(dep, seen)
        for key, (path, tree) in new_nodes().items():
            if key[0] in {"payments", "encryption"}:
                visit(key, set())
                self.assertNotIn("event_reimbursements", path.read_text(encoding="utf8"))

    def test_all_35_lane_models_and_attendance_marker_have_scalar_and_fk_migrations(self):
        expected = {}
        for package in ("event_reimbursements", "events/staged_forms", "payments/event_payouts"):
            doc = json.loads((BACKEND / "apps" / package / "manifest.json").read_text())
            for model in doc["models"]:
                expected[tuple(model["label"].lower().split("."))] = set(model["fields"])
        observed = defaultdict(set)
        for (app, _), (_, tree) in new_nodes().items():
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                args = {k.arg: k.value for k in call.keywords}
                if call.func.attr == "CreateModel":
                    name = ast.literal_eval(args["name"]).lower()
                    observed[(app, name)].update(ast.literal_eval(f.elts[0]) for f in args["fields"].elts)
                elif call.func.attr == "AddField":
                    observed[(app, ast.literal_eval(args["model_name"]))].add(ast.literal_eval(args["name"]))
        # 35 at the G1 checkpoint; the stage runtime, budget and finance follow-ups add 8.
        self.assertEqual(len(expected), 43)
        for model, fields in expected.items():
            self.assertEqual(observed[model], fields, model)
        self.assertIn(("events", "eventattendancecorrection"), observed)
        self.assertIn("attendance_revision", observed[("events", "eventregistration")])

    def test_all_pii_fields_have_retained_mappings_and_mandatory_fields_cannot_fall_back(self):
        for package in ("event_reimbursements", "events/staged_forms", "payments/event_payouts"):
            doc = json.loads((BACKEND / "apps" / package / "manifest.json").read_text())
            for model in doc["models"]:
                mapped = {f.field_name: f for f in fields_for_label(model["label"])}
                expected = {name: f for name, f in model["fields"].items() if f["pii"]}
                self.assertEqual(set(mapped), set(expected), model["label"])
                for name, item in expected.items():
                    self.assertEqual(mapped[name].encryption_required, item["encryption_required"])
                    self.assertEqual(mapped[name].makerspace_path, model["scope"])

    def test_module_and_fixed_role_grants_are_default_off_and_do_not_broaden_others(self):
        module = BY_KEY["event_reimbursements"]
        self.assertFalse(module.default_enabled)
        self.assertFalse(module.is_core)
        self.assertEqual(module.requires_modules, ("events",))
        for slug, role in ROLE_BY_SLUG.items():
            self.assertEqual("record_reimbursement_payout" in role.granted_actions, slug == "space_manager")
        tree = ast.parse((BACKEND / "apps/makerspaces/migrations/0106_reimbursement_payout_action.py").read_text())
        self.assertTrue(any(isinstance(n, ast.FunctionDef) and n.name == "backwards" for n in tree.body))

    def test_guards_are_reversible_and_new_tables_do_not_implicitly_enable_runtime(self):
        for key, (path, tree) in new_nodes().items():
            for call in ast.walk(tree):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "RunSQL":
                    self.assertGreaterEqual(len(call.args), 2, path.name)
            self.assertLessEqual(len(path.read_text().splitlines()), 300, path.name)
        reimbursement = (BACKEND / "apps/event_reimbursements/migrations/0001_reimbursement_tables_1.py").read_text()
        self.assertIn("models.BooleanField(default=False)", reimbursement)
        for _, (path, _) in new_nodes().items():
            self.assertNotIn("enabled_modules", path.read_text())

    def test_events_tombstone_removes_reimbursement_runtime_but_not_core(self):
        from apps.separability.tombstones import tombstoned_app_labels
        with patch.dict("os.environ", {"TOMBSTONED_APPS": "events,payments"}):
            labels = tombstoned_app_labels()
        self.assertIn("event_reimbursements", labels)
        self.assertIn("events", labels)
        self.assertIn("payments_rail", labels)
        self.assertNotIn("payments", labels)


if __name__ == "__main__":
    unittest.main()
