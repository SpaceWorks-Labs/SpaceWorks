"""scripts/ci/check_version_bump.py: every merge to main bumps VERSION, consistently."""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location("check_version_bump", REPO / "scripts" / "ci" / "check_version_bump.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bump = _load()


def _tree(root: Path, version: str = "0.12.0", **overrides) -> Path:
    """A minimal repo whose version carriers all agree with `version`."""
    files = {
        "VERSION": f"{version}\n",
        "backend/config/settings_schema.py": f'    "VERSION": "{version}",\n',
        "frontend/openapi-schema.json": f'{{\n  "info": {{\n    "version": "{version}",\n  }}\n}}\n',
        "README.md": f'<img src="https://img.shields.io/badge/version-{version}-006E63?style=flat-square">\n',
        f"docs/release-{version}.md": "# notes\n",
    }
    files.update(overrides)
    for rel, text in files.items():
        if text is None:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _files(errors):
    return [rel for rel, _ in errors]


def test_greater_version_passes(tmp_path):
    assert bump.check(_tree(tmp_path), "0.11.9", None) == []


@pytest.mark.parametrize("base", ["0.9.9", "0.11.10", "0.12.0-rc"])
def test_numeric_not_lexical_comparison_or_nonsemver_base(tmp_path, base):
    errors = bump.check(_tree(tmp_path), base, None)
    assert (errors == []) == (base != "0.12.0-rc")


def test_equal_version_fails(tmp_path):
    errors = bump.check(_tree(tmp_path), "0.12.0", None)
    assert _files(errors) == ["VERSION"]
    assert "equal to" in errors[0][1]


def test_lower_version_fails(tmp_path):
    errors = bump.check(_tree(tmp_path), "0.13.0", None)
    assert "lower than" in errors[0][1]


@pytest.mark.parametrize("head", ["", "1.2", "v1.2.3", "1.2.3-main.4"])
def test_invalid_head_version_fails(tmp_path, head):
    errors = bump.check(_tree(tmp_path, VERSION=f"{head}\n"), "0.1.0", None)
    assert _files(errors) == ["VERSION"] and "semantic version" in errors[0][1]


@pytest.mark.parametrize(
    "rel,text",
    [
        ("backend/config/settings_schema.py", '"VERSION": "0.11.0",'),
        ("frontend/openapi-schema.json", '"version": "0.11.0",'),
        ("README.md", "badge/version-0.11.0-006E63"),
    ],
)
def test_mismatched_carrier_fails(tmp_path, rel, text):
    errors = bump.check(_tree(tmp_path, **{rel: text}), "0.11.0", None)
    assert _files(errors) == [rel]


def test_missing_release_notes_fail(tmp_path):
    (_tree(tmp_path) / "docs" / "release-0.12.0.md").unlink()
    assert _files(bump.check(tmp_path, "0.11.0", None)) == ["docs/release-0.12.0.md"]


def test_existing_tag_fails_and_unrelated_tags_pass(tmp_path):
    _tree(tmp_path)
    assert bump.check(tmp_path, "0.11.0", {"v0.11.0-main.3.abc", "v0.12.01"}) == []
    assert _files(bump.check(tmp_path, "0.11.0", {"v0.12.0-main.7.abcdef012345"})) == ["VERSION"]
    assert _files(bump.check(tmp_path, "0.11.0", {"v0.12.0"})) == ["VERSION"]


def test_cli_exit_codes_and_annotation(tmp_path, capsys):
    _tree(tmp_path)
    assert bump.main(["--root", str(tmp_path), "--base-version", "0.11.0"]) == 0
    assert bump.main(["--root", str(tmp_path), "--base-version", "0.12.0"]) == 1
    assert "::error file=VERSION::" in capsys.readouterr().out
