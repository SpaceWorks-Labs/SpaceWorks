#!/usr/bin/env python3
"""Host-cloud initialization and offline-first managed deployment setup."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def render_compose_config(compose_path, static_env, pointer_path):
    """Render Compose only in this root-owned host process, never in Django."""
    scrubbed = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR"}
    }
    completed = subprocess.run(
        [
            "docker", "compose", "--env-file", str(static_env),
            "--env-file", str(pointer_path), "-f", str(compose_path), "config",
        ],
        env=scrubbed,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return completed.stdout


def host_main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init-from-current-environment",))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--ops-dir", default="/var/lib/spaceworks/ops")
    parser.add_argument("--static-env", default="/etc/spaceworks/cloud.env")
    parser.add_argument("--compose", default=str(ROOT / "docker-compose.cloud.yml"))
    args = parser.parse_args(argv)
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise RuntimeError("Cloud environment initialization must run as root.")
    sys.path.insert(0, str(ROOT / "backend"))
    from apps.backup.host_supervisor import supervise_run
    from cloud_setup.host_commit import commit_host_environment

    ops = Path(args.ops_dir)
    with supervise_run(
        ops,
        run_id=args.run_id,
        artifact_sha256=args.artifact_sha256,
        phases=("cloud-config-initialization",),
    ) as session:
        if session.resume.phase is None:
            raise RuntimeError("Cloud environment was already initialized for this run.")
        begun = session.ledger.begin(
            "cloud-config-initialization", {"source": "invoking-environment"}
        )
        result = commit_host_environment(ops=ops, static_env=args.static_env, compose=args.compose, renderer=render_compose_config)
        session.ledger.finish(begun, result)
    print(json.dumps(result, sort_keys=True))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "init-from-current-environment":
        try:
            return host_main(argv)
        except Exception:
            print(json.dumps({"status": "failed", "code": "host_initialization_failed", "action": "Inspect the private host ledger; resume under the same operation lock."}), file=sys.stderr)
            return 78
    if not argv or argv[0] in {"--help", "-h"}:
        parser = argparse.ArgumentParser(description="Space Works deployment setup. Host: init-from-current-environment. Managed: wizard, validate, render, bootstrap. Run ACTION --help for options; help imports no Django.")
        parser.add_argument("action", nargs="?", choices=("init-from-current-environment", "wizard", "validate", "render", "bootstrap"))
        parser.parse_args(argv or ["--help"])
        return 0
    from cloud_setup.cli import main as managed_main
    return managed_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
