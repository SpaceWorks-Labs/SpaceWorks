"""Exercise only dev.sh's argument adapter, with infrastructure replaced by a printer."""
import os
import subprocess

import pytest

from tests.areas import ROOT


def _adapter(args, *, expression="area_events", selector_status=0, entrypoint=""):
    source = (ROOT / "scripts/dev.sh").read_text(encoding="utf-8")
    function = "test_areas() {" + source.split("test_areas() {", 1)[1].split("\ntest_suite() {", 1)[0]
    script = r'''
set -euo pipefail
HOST_ROOT=/unused
python() { printf '%s\n' "$SELECTOR_OUTPUT"; return "$SELECTOR_STATUS"; }
test_suite() { printf 'RUN\0'; if (($#)); then printf '%s\0' "$@"; fi; }
''' + function + '\ntest_areas "$@"\n'
    return subprocess.run(["bash", "-c", script, "adapter", *args], capture_output=True,
                          env={**os.environ, "SELECTOR_OUTPUT": expression, "SELECTOR_STATUS": str(selector_status),
                               "TEST_ENTRYPOINT": entrypoint})


def _arguments(result):
    return result.stdout.decode().rstrip("\0").split("\0")


def test_no_area_arguments_are_forwarded_unchanged():
    result = _adapter(["-q", "tests/events", "-m", "not migration"])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-q", "tests/events", "-m", "not migration"]


def test_no_arguments_preserve_the_existing_default():
    result = _adapter([])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN"]


def test_repeatable_areas_union_and_combine_with_existing_marker():
    result = _adapter(["--area", "events", "--area", "bookings", "-m", "not migration", "-q"],
                      expression="area_bookings or area_events")
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-q", "-m", "(area_bookings or area_events) and (not migration)"]


def test_equals_area_form_and_compact_marker_are_supported():
    result = _adapter(["--area=events", "-mnot migration"])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-m", "(area_events) and (not migration)"]


@pytest.mark.parametrize("marker_args", [
    ["-m", "not migration"], ["-mnot migration"], ["-m=not migration"],
    ["--markexpr", "not migration"], ["--markexpr=not migration"],
])
def test_area_composes_every_marker_alias_without_losing_other_arguments(marker_args):
    result = _adapter(["tests/events", *marker_args, "--area", "events", "-q"])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "tests/events", "-q", "-m", "(area_events) and (not migration)"]


@pytest.mark.parametrize("marker_args", [
    ["-m", "migration", "--markexpr", "not migration"],
    ["--markexpr=migration", "-m=not migration"],
    ["-mmigration", "--markexpr=not migration"],
    ["--markexpr", "migration", "-m", "not migration"],
    ["-m=migration", "-mnot migration"],
])
def test_area_preserves_last_explicit_marker_across_mixed_aliases(marker_args):
    result = _adapter(["--area", "events", "-q", *marker_args])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-q", "-m", "(area_events) and (not migration)"]


@pytest.mark.parametrize("option", ["-m", "--markexpr"])
@pytest.mark.parametrize("tail", [[], ["-q"], ["--markexpr=not migration"]])
def test_missing_marker_values_refuse_before_the_runner(option, tail):
    result = _adapter(["--area", "events", option, *tail])
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == f"{option} needs an expression\n".encode()


@pytest.mark.parametrize("marker_args", [
    ["-m", ""], ["-m="], ["--markexpr", ""], ["--markexpr="],
])
def test_explicit_empty_last_marker_clears_the_previous_filter(marker_args):
    result = _adapter(["--area", "events", "-m", "migration", *marker_args])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-m", "area_events"]


@pytest.mark.parametrize("marker_args", [
    ["-m", "not migration"], ["-mnot migration"], ["-m=not migration"],
    ["--markexpr", "not migration"], ["--markexpr=not migration"],
    ["--markexpr", "migration", "-m=not migration"], ["--markexpr"], ["--markers"],
])
def test_no_area_preserves_marker_arguments_verbatim(marker_args):
    result = _adapter(["-q", *marker_args])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-q", *marker_args]


def test_markers_listing_is_forwarded_alongside_the_area_filter():
    result = _adapter(["--area", "events", "--markers"])
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "--markers", "-m", "area_events"]


def test_shared_change_selects_full_suite_without_losing_other_arguments():
    result = _adapter(["--area-affected", "base", "-q", "--maxfail=1"], expression="ALL")
    assert result.returncode == 0
    assert _arguments(result) == ["RUN", "-q", "--maxfail=1"]


def test_empty_diff_does_not_start_the_runner():
    result = _adapter(["--area-affected", "base"], expression="NONE")
    assert result.returncode == 0
    assert result.stdout == b"No changed areas.\n"


@pytest.mark.parametrize("args", [["--area"], ["--area-affected"], ["--area", "--maxfail=1"],
                                      ["--area", ""]])
def test_missing_values_are_rejected_before_infrastructure(args):
    result = _adapter(args)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"needs a value; list areas:" in result.stderr


def test_invalid_area_or_reference_does_not_start_the_runner():
    result = _adapter(["--area", "unknown"], expression="", selector_status=2)
    assert result.returncode == 2
    assert result.stdout == b""


def test_area_selection_refuses_non_pytest_entrypoints():
    result = _adapter(["--area", "events"], entrypoint="python")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b"Area selection requires pytest (unset TEST_ENTRYPOINT).\n"


def test_runner_failure_is_preserved():
    # A failing selector is handled above; an actual runner failure must also reach CI.
    source = (ROOT / "scripts/dev.sh").read_text(encoding="utf-8")
    function = "test_areas() {" + source.split("test_areas() {", 1)[1].split("\ntest_suite() {", 1)[0]
    script = 'set -euo pipefail\nHOST_ROOT=/unused\npython() { echo area_events; }\ntest_suite() { return 7; }\n'
    result = subprocess.run(["bash", "-c", script + function + '\ntest_areas --area events'],
                            capture_output=True, env={**os.environ, "TEST_ENTRYPOINT": ""})
    assert result.returncode == 7
    assert result.stdout == b""
