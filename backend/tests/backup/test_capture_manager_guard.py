"""Guard: capture, restore, migration and export never read through a filtered default manager.

Since one account per person, ``MakerspaceMembership.objects`` is community-only. A generic
``model.objects`` loop over a tenant's datasets therefore dropped every staff-track row from
per-space archives, tenant dumps and exports, and a per-space restore then deleted the
space's staff. Code in the four whole-tenant apps must read a model it did not name through
``apps.backup.capture_managers.every_row`` (local only, never committed).
"""

import ast
from pathlib import Path

import pytest
from django.apps import apps

from apps.backup.capture_managers import FILTERED_DEFAULT_MANAGERS, every_row

APPS_ROOT = Path(__file__).resolve().parents[2] / "apps"
SCANNED = ("backup", "tenant_migration", "data_export", "separability")
# U-C: account deletion/purge and the tenant purge are whole-account / whole-tenant reads too
# (the per-space restore calls account_purge_scrub.scrub_tenant).
SCANNED_FILES = ("accounts/account_purge*.py", "accounts/account_deletion*.py", "makerspaces/lifecycle_purge*.py")

# (file, receiver) pairs whose `.objects` is not a generic dataset read.
EXEMPT_RECEIVERS = {
    ("backup/models.py", "cls"): "singleton settings row",
    ("backup/models_host_identity.py", "cls"): "singleton host identity row",
    ("backup/models_restore.py", "cls"): "singleton recovery-state row",
    ("backup/recovery.py", "challenge"): "loop over five named challenge models",
    ("backup/space_restore_objects.py", "archive"): "SpaceArchive.objects() is a method",
    ("backup/space_restore_preview.py", "archive"): "SpaceArchive.objects() is a method",
    ("backup/space_restore_runner.py", "space.__class__"): "the Makerspace row itself",
    ("tenant_migration/target_cutover.py", "import_job.__class__"): "the import job row itself",
    ("tenant_migration/tenant_restore_objects.py", "type(makerspace)"): "the Makerspace row itself",
    ("makerspaces/lifecycle_purge.py", "makerspace.__class__"): "the Makerspace row itself",
}
RELATED_READS = {"all", "filter", "exclude", "get", "values", "values_list", "count", "exists",
                 "iterator", "order_by", "select_related", "first", "last"}


def _filtered(manager):
    return bool(manager.all().query.where)


def _filtered_class_names():
    return {apps.get_model(label).__name__ for label in FILTERED_DEFAULT_MANAGERS} | {"Membership"}


@pytest.mark.django_db
def test_every_filtered_default_manager_is_declared():
    filtered = {model._meta.label for model in apps.get_models() if _filtered(model._default_manager)}
    assert filtered == set(FILTERED_DEFAULT_MANAGERS)


@pytest.mark.django_db
def test_base_managers_and_every_row_see_every_row():
    for model in apps.get_models():
        assert not _filtered(model._base_manager), model._meta.label
        assert not _filtered(every_row(model)), model._meta.label


def _sites():
    filtered_names = _filtered_class_names()
    problems = []
    paths = [path for folder in SCANNED for path in sorted((APPS_ROOT / folder).rglob("*.py"))]
    paths += [path for pattern in SCANNED_FILES for path in sorted(APPS_ROOT.glob(pattern))]
    for path in paths:
        if True:
            relative = path.relative_to(APPS_ROOT).as_posix()
            if "migrations" in path.parts or relative == "backup/capture_managers.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Attribute) and node.attr in {"objects", "_default_manager"}:
                    receiver = ast.unparse(node.value)
                    concrete = isinstance(node.value, ast.Name) and receiver[:1].isupper()
                    if node.attr == "_default_manager" or receiver in filtered_names or (
                            not concrete and (relative, receiver) not in EXEMPT_RECEIVERS):
                        problems.append(f"{relative}:{node.lineno}: {receiver}.{node.attr}")
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in RELATED_READS and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr in {"memberships", "makerspace_memberships"}
                        and ast.unparse(node.func.value.value) != "self"):
                    problems.append(f"{relative}:{node.lineno}: reverse {ast.unparse(node.func.value)}")
    return problems


def test_capture_paths_never_read_a_filtered_default_manager():
    assert _sites() == []


def test_purge_and_deletion_files_are_scanned():
    assert all(list(APPS_ROOT.glob(pattern)) for pattern in SCANNED_FILES)


def test_exemptions_are_live():
    seen = set()
    for relative, receiver in EXEMPT_RECEIVERS:
        tree = ast.parse((APPS_ROOT / relative).read_text(encoding="utf-8"))
        if any(isinstance(node, ast.Attribute) and node.attr == "objects"
               and ast.unparse(node.value) == receiver for node in ast.walk(tree)):
            seen.add((relative, receiver))
    assert seen == set(EXEMPT_RECEIVERS)
