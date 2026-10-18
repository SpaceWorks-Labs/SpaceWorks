"""Private artifacts, with runtime/release custody separated before serialization."""

import hashlib
import json
from pathlib import Path

from .environment import command, role_environment
from .errors import SetupError
from .private_files import write_json, write_private
from .free_profile import tick_cron


def dotenv(values):
    # Compose-style quoted dotenv is data, never shell-sourced. JSON is the
    # canonical transport for environments; dotenv is convenience for operators.
    return "".join(f"{key}={json.dumps(value)}\n" for key, value in sorted(values.items()))


def render(directory, values, answers):
    root = Path(directory) / "rendered"
    runtime = role_environment(values, "web")
    release = role_environment(values, "release")
    roles = ["web"]
    if answers["profile"] == "full":
        roles += ["worker", "beat" if answers["task_profile"] == "redis" else "scheduler"]
    spec = {
        "version": 1, "deployment_mode": "managed", "profile": answers["profile"],
        "backend_image": answers["backend_image"],
        "image_variant": "free" if answers["profile"] == "free" else "full",
        "scheduler": values["CLOUD_SCHEDULER"],
        "roles": [{"name": role, "argv": command(role), "replicas": 1} for role in roles],
        "release": {"argv": command("release"), "finite": True, "environment": "release.environment.json"},
        "frontend": {"apiUrl": "/api", "upstream": answers["api_origin"], "browser_internal_routes": "denied", "worker_cron": tick_cron(int(values["FREE_TICK_INTERVAL_SECONDS"])) if answers["profile"] == "free" else None},
        "completion": "pending runtime, core-flow and provider acceptance",
    }
    files = {
        "runtime.environment.json": json.dumps(runtime, indent=2, sort_keys=True) + "\n",
        "release.environment.json": json.dumps(release, indent=2, sort_keys=True) + "\n",
        "runtime.env": dotenv(runtime), "release.env": dotenv(release),
        "deployment.json": json.dumps(spec, indent=2, sort_keys=True) + "\n",
    }
    for name, payload in files.items():
        write_private(root / name, payload)
    from .recipes import render_native
    render_native(directory, values, answers)
    # Names/hashes only in the receipt. Raw environment is never returned/printed.
    receipt = {"version": 1, "status": "rendered", "files": [{"name": name, "sha256": hashlib.sha256(payload.encode()).hexdigest()} for name, payload in files.items()]}
    write_json(root / "receipt.json", receipt)
    return receipt
