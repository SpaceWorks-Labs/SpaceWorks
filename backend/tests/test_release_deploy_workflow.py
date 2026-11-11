"""The only server runner job consumes a published version without checking out code."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


def test_release_job_is_opt_in_main_only_and_waits_for_publication():
    workflow = yaml.safe_load((WORKFLOWS / "release.yml").read_text())
    deploy = workflow["jobs"]["deploy"]
    assert deploy["runs-on"] == ["self-hosted", "spaceworks-prod"]
    assert deploy["if"] == "github.ref == 'refs/heads/main' && vars.SPACEWORKS_DEPLOY == 'true' && needs.promote-latest.outputs.eligible == 'true'"
    assert set(deploy["needs"]) >= {"prepare", "publish", "github-release", "promote-latest"}
    assert deploy["environment"] == "production"
    assert deploy["permissions"] == {}
    assert deploy["timeout-minutes"] >= 60
    assert deploy["concurrency"] == {"group": "spaceworks-prod-deploy", "cancel-in-progress": False}
    assert len(deploy["steps"]) == 1
    for step in deploy["steps"]:
        assert "uses" not in step
        assert "${{" not in step["run"]
        assert step["env"]["VERSION"] == "${{ needs.prepare.outputs.version }}"
        assert 'bash "${SPACEWORKS_DIR:-/opt/spaceworks}/scripts/update.sh"' in step["run"]
        assert '--force --no-module-changes --version "$VERSION"' in step["run"]


def test_no_other_job_or_workflow_can_target_the_server_runner():
    for path in WORKFLOWS.iterdir():
        if path.suffix not in {".yml", ".yaml"}:
            continue
        document = yaml.safe_load(path.read_text())
        for name, job in document["jobs"].items():
            if path.name == "release.yml" and name == "deploy":
                continue
            assert "self-hosted" not in str(job)
            assert "spaceworks-prod" not in str(job)


def test_multiarchitecture_build_and_queued_deploy_rechecks_main():
    workflow = yaml.safe_load((WORKFLOWS / "release.yml").read_text())
    jobs = workflow["jobs"]
    steps = jobs["publish"]["steps"]
    assert any(step.get("uses") == "docker/setup-qemu-action@v3" for step in steps)
    build = next(step for step in steps if step.get("uses") == "docker/build-push-action@v6")
    assert build["with"]["platforms"] == "linux/amd64,linux/arm64"
    assert jobs["promote-latest"]["outputs"]["eligible"] == "${{ steps.head.outputs.current }}"
    deploy = jobs["deploy"]["steps"][0]["run"]
    assert deploy.index("/commits/main") < deploy.index("scripts/update.sh")
    assert '"${BASH_REMATCH[1]}" != "$GITHUB_SHA"' in deploy
