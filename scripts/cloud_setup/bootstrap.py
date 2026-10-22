"""Finite release invocation with no maintenance credentials in web startup."""

import os
from pathlib import Path
import subprocess
import sys

from .errors import SetupError
from .service_probes import email_probe, readiness
from .storage_probe import storage_probe
from .validation import probe, validate
from .private_files import write_json

_ROOT = Path(__file__).resolve().parents[2]
BACKEND = _ROOT / "backend" if (_ROOT / "backend/manage.py").is_file() else _ROOT


def release(values):
    # Execute the frozen release-role interface, never a caller-selected command.
    # The release role owns the DB lock/migrations/grants/idempotent setup sequence.
    # Only copy the minimal host execution environment, not ambient PG/Python flags.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR") if key in os.environ}
    env.update(values, DJANGO_SETTINGS_MODULE="config.settings")
    try:
        subprocess.run(
            [sys.executable, "scripts/cloud_entrypoint.py", "--role", "migrate", "python", "-m", "scripts.run_cloud_role", "release"],
            cwd=BACKEND, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise SetupError("release_failed", "The finite release failed. Inspect protected provider diagnostics; retain state and rerun after correction.") from None
    return {"status": "passed"}


def bootstrap(directory, values, answers, *, send_test=False, inbox_confirmed=False, acceptance_file=None, release_only=False):
    root = Path(directory)
    report = validate(values, answers)
    if report["status"] != "passed":
        write_json(root / "bootstrap.json", report)
        return report
    # A release is intentionally idempotent and re-runs its server-owned lock and
    # identity checks on every resume. A local done flag cannot skip those gates.
    phase = {"version": 1, "status": "incomplete", "phase": "release", "checks": []}
    write_json(root / "bootstrap.json", phase)
    phase["checks"].append(probe("release", lambda: release(values)))
    if release_only and phase["checks"][-1]["status"] == "passed":
        phase.update(status="released", phase="awaiting-deployment", action="Deploy runtime-only services from rendered artifacts, then run post-deploy bootstrap acceptance. Setup is not complete.")
        write_json(root / "bootstrap.json", phase)
        return phase
    if phase["checks"][-1]["status"] == "passed":
        phase["phase"] = "verification"
        write_json(root / "bootstrap.json", phase)
        phase["checks"].append(probe("storage", lambda: storage_probe(values, answers)))
        phase["checks"].append(probe("readiness", lambda: readiness(answers["api_origin"])))
        final = validate(values, answers, final=True)
        phase["checks"].extend(final["checks"])
        if send_test:
            phase["checks"].append(probe("test_mail", lambda: send_in_environment(values, answers)))
        from .completion import verify_acceptance
        phase["checks"].append(probe("runtime_flows", lambda: verify_acceptance(acceptance_file, values, answers)))
    passed = all(item["status"] == "passed" for item in phase["checks"])
    if passed and send_test and inbox_confirmed:
        phase.update(status="complete", phase="complete")
    else:
        phase["action"] = "Resolve failed checks, request a test email, confirm inbox receipt, and rerun bootstrap. Completion is never inferred from API acceptance."
    write_json(root / "bootstrap.json", phase)
    return phase


def send_in_environment(values, answers):
    # Django settings are lazy but process-global; this CLI is a short-lived
    # one-off, and env installation happens only after the release phase.
    os.environ.update(values, DJANGO_SETTINGS_MODULE="config.settings")
    from .secret_files import materialize_secret_files
    materialize_secret_files(os.environ)
    sys.path.insert(0, str(BACKEND))
    return email_probe(values, answers, send=True)


