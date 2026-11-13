"""Ownership drift guards and selectors. These tests do not start infrastructure."""
from collections import Counter
from configparser import ConfigParser
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from tests import areas


def test_every_backend_test_file_has_an_area():
    missing = [path.relative_to(areas.BACKEND).as_posix()
               for path in sorted((areas.BACKEND / "tests").rglob("test_*.py"))
               if not areas.areas_for_test(path)]
    assert missing == [], "Add explicit ownership in tests/areas.py: " + ", ".join(missing)


def test_print_area_file_counts():
    counts = Counter(name for path in (areas.BACKEND / "tests").rglob("test_*.py")
                     for name in areas.areas_for_test(path))
    print("\nArea test-file counts (overlap is intentional):")
    for name in sorted(areas.AREAS):
        print(f"{name}: {counts[name]}")
    assert set(counts) == set(areas.AREAS)


def test_every_area_marker_is_registered_and_frontend_names_match():
    config = ConfigParser()
    config.read(areas.BACKEND / "pytest.ini")
    markers = {line.split(":")[0] for line in config["pytest"]["markers"].splitlines() if line.startswith("area_")}
    assert markers == {f"area_{name}" for name in areas.AREAS}
    frontend = (areas.ROOT / "frontend/src/test/areas.ts").read_text(encoding="utf-8")
    block = frontend.split("export const areas:", 1)[1].split("};", 1)[0]
    assert set(re.findall(r"^  ([a-z_]+):", block, re.MULTILINE)) == set(areas.AREAS)


def test_all_shipped_backend_apps_have_area_ownership():
    apps = {p.name for p in (areas.BACKEND / "apps").iterdir() if p.is_dir() and not p.name.startswith("_")}
    assert sorted(app for app in apps if not areas.owners_for_app(app)) == []


def test_every_frontend_feature_directory_has_affected_area_ownership():
    features = (areas.ROOT / "frontend/src/features").iterdir()
    assert sorted(path.name for path in features if path.is_dir() and not areas.owners_for_feature(path.name)) == []


@pytest.fixture
def isolated_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(areas, "BACKEND", tmp_path)
    for function in (areas.areas_for_test, areas._direct_owners, areas._references):
        function.cache_clear()
    yield tmp_path
    for function in (areas.areas_for_test, areas._direct_owners, areas._references):
        function.cache_clear()


def _write(root, name, source):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_unknown_paths_are_not_hidden_by_a_catch_all(isolated_backend):
    path = _write(isolated_backend, "tests/new_domain/test_unknown.py", "def test_x(): pass\n")
    assert areas.areas_for_test(path) == frozenset()


def test_path_and_imports_and_literal_module_keys_all_contribute(isolated_backend):
    path = _write(isolated_backend, "tests/audit/test_cross.py",
                  "from apps.bookings.models import Booking\nMODULE = 'events'\n")
    assert areas.areas_for_test(path) == frozenset({"audit", "bookings", "events"})


def test_helper_imports_and_relative_imports_are_followed_without_execution(isolated_backend):
    _write(isolated_backend, "tests/ambiguous/helper.py", "raise RuntimeError('never execute')\nfrom apps.shop import models\n")
    path = _write(isolated_backend, "tests/ambiguous/test_cross.py", "from .helper import unused\n")
    assert areas.areas_for_test(path) == frozenset({"shop"})


def test_cyclic_helper_imports_terminate_and_keep_both_owners(isolated_backend):
    _write(isolated_backend, "tests/ambiguous/a.py", "from .b import b\nfrom apps.shop import models\n")
    _write(isolated_backend, "tests/ambiguous/b.py", "from .a import a\nfrom apps.events import models\n")
    path = _write(isolated_backend, "tests/ambiguous/test_cross.py", "from .a import a\n")
    assert areas.areas_for_test(path) == frozenset({"shop", "events"})


def test_string_imports_and_parentless_money_capabilities_are_owned(isolated_backend):
    path = _write(isolated_backend, "tests/ambiguous/test_dynamic.py",
                  "TARGET = 'apps.evidence.storage.validate'\nKEY = 'charges.enabled'\n")
    assert areas.areas_for_test(path) == frozenset({"lending", "evidence_uploads", "payments_ledger"})


def test_duplicate_area_arguments_produce_a_stable_union():
    assert areas.marker_expression(["events", "bookings", "events"]) == "area_bookings or area_events"


def test_unknown_area_is_an_error():
    with pytest.raises(ValueError) as caught:
        areas.marker_expression(["eventz"])
    assert str(caught.value) == "Unknown areas: eventz; use --list"


def test_affected_parent_includes_dependent_and_dependent_includes_parent():
    assert areas.affected(["backend/apps/events/views.py"]) == {"events", "event_reimbursements"}
    assert areas.affected(["backend/apps/event_reimbursements/models.py"]) == {"events", "event_reimbursements"}


def test_affected_dependency_graph_reaches_siblings_through_parent():
    assert areas.interconnected({"mobile"}) == {"mobile", "member_accounts", "membership"}


def test_frontend_feature_changes_use_backend_area_names():
    assert areas.affected(["frontend/src/features/events/Detail.tsx"]) == {"events", "event_reimbursements"}
    assert areas.affected(["frontend/src/features/payments/Checkout.tsx"]) == {"payments", "payments_ledger"}


@pytest.mark.parametrize("path", ["backend/conftest.py", "backend/config/settings.py", "scripts/dev.sh",
                                      "backend/apps/new_app/models.py", "backend/apps/makerspaces/module_registry_catalog.py",
                                      "frontend/src/features/newFeature/Screen.tsx",
                                      "frontend/src/lib/api.ts", "backend/tests/areas.py"])
def test_shared_or_unknown_changes_require_the_full_suite(path):
    assert areas.affected([path]) is None


def test_empty_diff_has_no_affected_areas():
    assert areas.affected([]) == set()


def test_cli_rejects_an_empty_reference(capsys):
    with pytest.raises(SystemExit) as caught:
        areas.main(["--area-affected="])
    assert caught.value.code == 2
    assert "--area-affected needs a non-empty ref" in capsys.readouterr().err


def test_cli_uses_nul_delimited_paths_and_unions_explicit_areas(monkeypatch, capsys):
    calls = []

    def diff(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=b"backend/apps/events/views.py\0")

    monkeypatch.setattr(areas.subprocess, "run", diff)
    areas.main(["--area", "bookings", "--area-affected", "release/base"])
    assert capsys.readouterr().out == "area_bookings or area_event_reimbursements or area_events\n"
    assert calls == [(["git", "diff", "--name-only", "-z", "--end-of-options", "release/base", "--"],
                      {"cwd": areas.ROOT, "capture_output": True, "check": True})]


def test_cli_rejects_unknown_names_before_reading_changes(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid names must not invoke the change reader")

    monkeypatch.setattr(areas.subprocess, "run", forbidden)
    with pytest.raises(SystemExit) as caught:
        areas.main(["--area", "eventz", "--area-affected", "HEAD"])
    assert caught.value.code == 2
    assert "Unknown areas: eventz; use --list" in capsys.readouterr().err


def test_backend_markers_include_parameterized_cross_area_cases():
    import conftest as hooks

    assert hooks._parameter_areas([("events", "bookings"), {"child": "event_reimbursements"}]) == {
        "events", "bookings", "event_reimbursements",
    }
    assert hooks._parameter_areas(["charges.events"]) == {"events", "payments_ledger"}


def test_parameter_ownership_handles_hostile_recursive_values():
    import conftest as hooks

    value = ["events"]
    value.append(value)
    assert hooks._parameter_areas([value]) == {"events"}


def test_invalid_reference_is_a_cli_error_without_selecting_tests(monkeypatch, capsys):
    def invalid(*args, **kwargs):
        raise areas.subprocess.CalledProcessError(128, ["git", "diff"])

    monkeypatch.setattr(areas.subprocess, "run", invalid)
    with pytest.raises(SystemExit) as caught:
        areas.main(["--area-affected", "missing-ref"])
    output = capsys.readouterr()
    assert caught.value.code == 2
    assert output.out == ""
    assert "returned non-zero exit status 128" in output.err


def test_backend_collection_keeps_migration_marker_and_adds_all_areas(monkeypatch):
    import conftest as hooks

    marks = []
    monkeypatch.setattr(hooks, "_drives_migrations", lambda path: True)
    monkeypatch.setattr(hooks, "areas_for_test", lambda path: {"audit"})
    item = SimpleNamespace(fspath=Path("test_cross.py"), add_marker=marks.append,
                           callspec=SimpleNamespace(params={"pair": ("events", "bookings")}))
    hooks.pytest_collection_modifyitems(None, [item])
    assert {mark.name for mark in marks} == {"migration", "area_audit", "area_events", "area_bookings"}
