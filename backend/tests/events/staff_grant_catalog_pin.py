"""Standalone catalog-pin evidence when this Windows host has no Django.

Run ``python backend/tests/events/staff_grant_catalog_pin.py`` from the worktree.
This supplements, never replaces, the live ``validate_catalog`` Django test.
"""

import ast
import hashlib
import json
from pathlib import Path


BASELINE_PIN = "971cdeb8cbf63d0d5461dc51d9085fd7ad6bba7480fcaf638cdd9de392b4b2d7"
ROOT = Path(__file__).resolve().parents[2] / "apps"
SNAPSHOTS = (
    "tenant_migration/catalog_7b.py", "tenant_migration/catalog_7c.py",
    "tenant_migration/catalog_w7_events.py", "tenant_migration/catalog_wp3.py",
    "tenant_migration/tenant_dump_modules.py", "data_export/classification_wp4.py",
    "tenant_migration/catalog_wp4.py", "tenant_migration/tenant_dump_field_snapshot.py",
)


def snapshot_rows():
    scope = {}
    for filename in SNAPSHOTS:
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        if filename.endswith("tenant_dump_modules.py"):
            tree.body = [node for node in tree.body if not isinstance(node, ast.Assign) or all(
                not isinstance(target, ast.Name) or target.id != "MODULE_AUTHORITY_ENTRIES"
                for target in node.targets
            )]
        exec(compile(tree, filename, "exec"), scope)
    rows = []
    for name, auto, managed in (
        ("FIRST_PARTY_FIELD_NAMES", False, True), ("AUTO_CREATED_FIELD_NAMES", True, True),
        ("THIRD_PARTY_FIELD_NAMES", False, True), ("UNMANAGED_FIELD_NAMES", False, False),
    ):
        for label, fields in scope[name].items():
            app, model = label.split(".")
            table = {"sessions.Session": "django_session", "admin.LogEntry": "django_admin_log",
                     "contenttypes.ContentType": "django_content_type"}.get(label, f"{app}_{model.lower()}")
            rows.append(dict(app_label=app, auto_created=auto, managed=managed,
                             db_table=table, label=label, fields=sorted(fields)))
    return rows


def digest(rows):
    graph = json.dumps(sorted(rows, key=lambda row: row["label"]), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(graph.encode()).hexdigest()


if __name__ == "__main__":
    current = snapshot_rows()
    baseline = [dict(row, fields=[field for field in row["fields"] if not (
        row["label"] == "makerspaces.Makerspace" and field == "event_default_registration_audience"
        or row["label"] == "integrations.NotificationTimingPolicy" and field == "daily_digest_default"
    )]) for row in current if row["label"] not in {"events.EventStaffGrant", "events.EventStaffGrantInvite"}]
    assert digest(baseline) == BASELINE_PIN, "The inferred base graph did not reproduce the reviewed pin."
    catalog = ast.parse((ROOT / "tenant_migration/tenant_dump_catalog.py").read_text(encoding="utf-8"))
    pin = next(ast.literal_eval(node.value) for node in catalog.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "CATALOG_SCHEMA_SHA256" for target in node.targets))
    assert digest(current) == pin, "The new literal graph does not match the updated pin."
    print(f"Baseline graph verified: {BASELINE_PIN}")
    print(f"Installer fields + Lane A grants verified: {pin}")
