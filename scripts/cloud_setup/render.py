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
    # This is a protected server-only adapter input, separate from browser build
    # configuration. It carries no database, storage or mail credentials.
    from urllib.parse import urlsplit
    def origin(value):
        parsed = urlsplit(value)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
    storage_origin = origin(values.get("AWS_S3_PUBLIC_ENDPOINT_URL", ""))
    edge = {"PUBLIC_ORIGIN": answers["public_origin"], "BACKEND_ORIGIN": answers["api_origin"],
            "SPACEWORKS_DEPLOYMENT_PROFILE": answers["profile"],
            "TRUSTED_EDGE_INGRESS_SECRET": values.get("TRUSTED_EDGE_INGRESS_SECRET", ""),
            "PUBLIC_API_URL": "/api", "CONNECT_ORIGINS": storage_origin,
            "IMAGE_ORIGINS": origin(values.get("PUBLIC_IMAGE_BASE_URL", "")),
            "MEDIA_ORIGINS": storage_origin}
    if answers["profile"] == "free":
        edge["FREE_TICK_SECRET"] = values["FREE_TICK_SECRET"]
    elif values.get("LIVE_ORIGIN"):
        edge["LIVE_ORIGIN"] = values["LIVE_ORIGIN"]
    roles = ["web"]
    if answers["profile"] == "full":
        roles += ["worker", "beat" if answers["task_profile"] == "redis" else "scheduler"]
    spec = {
        "version": 1, "deployment_mode": "managed", "profile": answers["profile"],
        "backend_image": answers["backend_image"],
        "image_variant": "full",
        "image_build": {"target": "release", "context": "backend", "named_context": "cloud_tooling=.", "verification": "Require the published release target and same-build immutable digest before deployment."},
        "scheduler": values["CLOUD_SCHEDULER"],
        "roles": [{"name": role, "argv": command(role), "replicas": 1} for role in roles],
        "release": {"argv": command("release"), "finite": True, "environment": "release.environment.json"},
        "frontend": {"apiUrl": "/api", "upstream": answers["api_origin"], "server_only_environment": "edge.environment.json", "browser_internal_routes": "denied", "worker_cron": tick_cron(int(values["FREE_TICK_INTERVAL_SECONDS"])) if answers["profile"] == "free" else None},
        "completion": "pending runtime, core-flow and provider acceptance",
    }
    files = {
        "runtime.environment.json": json.dumps(runtime, indent=2, sort_keys=True) + "\n",
        "edge.environment.json": json.dumps(edge, indent=2, sort_keys=True) + "\n",
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
