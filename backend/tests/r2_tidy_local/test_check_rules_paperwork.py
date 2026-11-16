"""scripts/ci/check_rules.py rule 3: no plans, prompts, hand-offs or research notes (#148b)."""
import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location("check_rules", REPO / "scripts" / "ci" / "check_rules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = _load()

# Paths #148 removed (02c9f018) or the .gitignore already kept local: each must be refused.
PAPERWORK = [
    "backend/apps/events/contributions/HANDOFF.md",
    "backend/apps/events/programme/LANE-F-HANDOFF.md",
    "backend/apps/events/programme/OPERATIONS-HANDOFF.md",
    "frontend/src/features/staff/eventProgramme/HANDOFF.md",
    "docs/account-deletion-part-b-handoff.md",
    "docs/setup-areas-handoff.md",
    "docs/design-revamp/PLAN.md",
    "docs/design-revamp/OWNERSHIP.md",
    "docs/design-revamp/research/tools/logo_build.py",
    "docs/design-revamp/research/logo-extract/symbol.svg",
    "docs/plans/r2/L20.md",
    "docs/PLAN-prd-1.md",
    "docs/billing-plan.md",
    "docs/HANDOVER.md",
    "docs/p2-presence.md",
    "PLAN.md",
    "plans/r2/LANE-RULES.md",
    "handover/HANDOVER.md",
    "handover/reports/L20.md",
    "briefs/sendmessages.md",
    "research/decisions-2026-10-18.md",
    "LANE-PROGRESS.md",
    "LANE-CLOUD-HANDOFF.md",
    "LANE-CLOUD-AUDIT/notes.md",
    "RECONCILIATION-FIELDS.md",
    "stage1-p7b.md",
    ".codex-prompt-lane.txt",
    "docs/review-prompt.md",
]

# Real product files whose names come close: none may be refused.
PRODUCT = [
    "README.md",
    "docs/README.md",
    "docs/member-account-renewals.md",
    "docs/report-infrastructure.md",
    "docs/KIOSK-RECOVERY.md",
    "frontend/src/help-content/en/handover/job-handover.md",
    "frontend/src/help-content/en/handover/direct-handout.md",
    "frontend/src/help-content/en/space-manager/membership-plans-and-admissions.md",
    "frontend/src/features/staff/handover/HandoverWizard.tsx",
    "backend/apps/membership/plan_services.py",
    "backend/apps/makerspaces/membership_plan_services.py",
    "frontend/src/features/staff/priceDrop/PriceDropDialog.tsx",
    "deploy/control-plane-true.caddy",
]


@pytest.mark.parametrize("path", PAPERWORK)
def test_planning_paperwork_is_refused(path):
    assert rules.planning_reason(path)


@pytest.mark.parametrize("path", PRODUCT)
def test_product_files_are_not_mistaken_for_paperwork(path):
    assert rules.planning_reason(path) is None


def _fake_ls_files(monkeypatch, paths):
    def run(args, **kwargs):
        assert args[:2] == ["git", "-C"] and "ls-files" in args
        return SimpleNamespace(stdout="\0".join(paths).encode("utf-8"))
    monkeypatch.setattr(rules.subprocess, "run", run)


def test_check_fails_on_a_tracked_hand_off_and_names_it(monkeypatch, capsys):
    _fake_ls_files(monkeypatch, ["README.md", "docs/x-handoff.md", "backend/apps/a.py"])
    assert rules.check_no_planning_files("/repo") == ["paperwork"]
    out = capsys.readouterr().out
    assert "docs/x-handoff.md" in out and "README.md" not in out.split("FAIL", 1)[1]


def test_check_passes_a_clean_tree_and_annotates_failures_on_ci(monkeypatch, capsys):
    _fake_ls_files(monkeypatch, PRODUCT)
    assert rules.check_no_planning_files("/repo") == []
    _fake_ls_files(monkeypatch, ["PLAN.md"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert rules.check_no_planning_files("/repo") == ["paperwork"]
    assert "::error file=PLAN.md::" in capsys.readouterr().out


def _git_works():  # R3: a linked worktree's .git file points at a host path the test container cannot see
    return shutil.which("git") is not None and subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=REPO, capture_output=True).returncode == 0


@pytest.mark.skipif(not _git_works(), reason="needs a usable git checkout (host check: scripts/ci/check_rules.py passes)")
def test_the_current_tree_passes_every_rule():
    result = subprocess.run(["python", str(REPO / "scripts" / "ci" / "check_rules.py")], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "[paperwork]" in result.stdout
