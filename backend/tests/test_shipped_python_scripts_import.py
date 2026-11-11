"""Every shipped Python script's module scope must execute without raising.

`scripts/validate-compose-wrapper.py` shipped with `ROOT = Path(...)` at module scope and
no `from pathlib import Path`, so it raised `NameError` before parsing a single argument.
`scripts/spaceworks-compose.sh` runs it (`set -euo pipefail`, then `"${VALIDATE[@]}"`)
BEFORE `exec docker compose`, so that one missing import aborted every compose command on
every topology - setup, update, restore and backup import alike. Nothing caught it because
no test executed the file: the wrapper is shell, and the suite only ever imported the
Django code these scripts call into.

The instrument is `exec_module`, not `--help`. Running module scope is exactly the failure
class - a missing import, a typo'd constant, a bad `sys.path` edit - while `main()` stays
behind its `__main__` guard, so scripts with different CLI conventions are not held to
argparse's exit codes. `bundled-database-url.py` takes a bare file path and would fail a
`--help` probe for reasons that say nothing about the module.

Subprocess rather than in-process import: these scripts insert `backend/` on `sys.path` and
import Django modules at module scope, and doing that inside the test session would leak
across tests.
"""

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not (ROOT / "install.sh").exists(),
    reason="host-only: the repository root is not in the backend image",
)

_EXEC_MODULE_SCOPE = """
import importlib.util
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))

spec = importlib.util.spec_from_file_location("shipped_script_under_test", sys.argv[1])
spec.loader.exec_module(importlib.util.module_from_spec(spec))
"""


def _shipped_python_scripts():
    return sorted([*ROOT.glob("scripts/*.py"), *ROOT.glob("scripts/installer/*.py")])


def test_the_scan_finds_the_shipped_python_scripts():
    """A glob that matched nothing would make every test below vacuously pass."""
    found = {path.name for path in _shipped_python_scripts()}
    assert "validate-compose-wrapper.py" in found, found
    assert len(found) >= 5, found


def _probe_capsule_members():
    """The runtime probes ship only inside probe-bundle.py's capsule, renamed to modules."""
    import ast

    tree = ast.parse((ROOT / "scripts/installer/probe-bundle.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "FILES":
            return frozenset(ast.literal_eval(node.value))
    raise AssertionError("probe-bundle.py no longer declares FILES")


def _as_shipped(script, tmp_path):
    """Run a capsule member from the capsule layout it actually ships in (a13352cd)."""
    if script.parent.name != "installer" or script.name not in _probe_capsule_members():
        return script
    for name in _probe_capsule_members():
        source = (script.parent / name).read_text(encoding="utf-8")
        (tmp_path / name.replace("-", "_")).write_text(source, encoding="utf-8")
    return tmp_path / script.name.replace("-", "_")


def test_probe_capsule_members_are_shipped_scripts():
    found = {path.name for path in _shipped_python_scripts()}
    assert _probe_capsule_members() <= found


@pytest.mark.parametrize("script", _shipped_python_scripts(), ids=lambda path: path.name)
def test_shipped_python_script_module_scope_executes(script, tmp_path):
    script = _as_shipped(script, tmp_path)
    completed = subprocess.run(
        [sys.executable, "-c", _EXEC_MODULE_SCOPE, str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )
    assert completed.returncode == 0, (
        f"{script.name} raised while executing module scope:\n"
        f"{completed.stdout}{completed.stderr}"
    )
