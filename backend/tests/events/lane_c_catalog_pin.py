"""Reconstruct the reviewed literal graph on hosts without Django; verify the base first."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOTS = (
    "catalog_7b.py", "catalog_7c.py", "catalog_w7_events.py", "catalog_wp3.py",
    "tenant_dump_modules.py", "../data_export/classification_wp4.py", "catalog_wp4.py",
    "tenant_dump_field_snapshot.py",
)


def read(name, baseline):
    path = (ROOT / "backend/apps/tenant_migration" / name).resolve()
    relative = path.relative_to(ROOT).as_posix()
    if baseline:
        return subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def graph(baseline=False):
    scope = {}
    exec(read("catalog_broadcasts.py", baseline), scope)
    scope["BROADCAST_FIELDS"] = scope["FIELD_NAMES"]
    if not baseline:
        exec(read("catalog_website.py", False), scope)
        scope["WEBSITE_FIELDS"] = scope["FIELD_NAMES"]
    for name in SNAPSHOTS:
        tree = ast.parse(read(name, baseline))
        tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
        if name == "tenant_dump_modules.py":
            tree.body = [n for n in tree.body if not isinstance(n, ast.Assign) or all(
                not isinstance(t, ast.Name) or t.id != "MODULE_AUTHORITY_ENTRIES" for t in n.targets)]
        exec(compile(tree, name, "exec"), scope)
    rows = []
    for name, auto, managed in (("FIRST_PARTY_FIELD_NAMES", False, True),
            ("AUTO_CREATED_FIELD_NAMES", True, True), ("THIRD_PARTY_FIELD_NAMES", False, True),
            ("UNMANAGED_FIELD_NAMES", False, False)):
        for label, fields in scope[name].items():
            app, model = label.split(".")
            table = {"sessions.Session": "django_session", "admin.LogEntry": "django_admin_log",
                     "contenttypes.ContentType": "django_content_type"}.get(label, f"{app}_{model.lower()}")
            rows.append(dict(app_label=app, auto_created=auto, managed=managed, db_table=table,
                             label=label, fields=sorted(fields)))
    return sorted(rows, key=lambda row: row["label"])


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pin(text):
    tree = ast.parse(text)
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "CATALOG_SCHEMA_SHA256" for t in n.targets))


if __name__ == "__main__":
    baseline = digest(graph(True))
    assert baseline == pin(read("tenant_dump_catalog.py", True)), baseline
    current = digest(graph())
    print(f"Reviewed baseline reproduced: {baseline}")
    print(f"Lane D model graph: {current}")
    text = read("tenant_dump_catalog.py", False)
    text = text.replace(pin(text), current)
    (ROOT / "backend/apps/tenant_migration/tenant_dump_catalog.py").write_text(text, encoding="utf-8", newline="\n")
    print("Catalog pin updated after reproducing HEAD.")
