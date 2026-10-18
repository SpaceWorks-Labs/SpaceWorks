"""Native Render and generic role manifests from one effective configuration."""

import json
from pathlib import Path

from .environment import command, role_environment
from .private_files import write_private

IMAGE_PLACEHOLDER = "ghcr.io/spaceworks-hq/spaceworks-backend@sha256:" + "0" * 64


def render_blueprint(values, answers, *, saas=False):
    runtime = role_environment(values, "web")
    # Values live in the provider's secret/config store. The separate private env
    # artifacts are uploaded explicitly; Blueprint contains names and fixed values.
    from .answers import FORBIDDEN_ENV, URL_SECRETS
    prompts = {key for key in runtime if FORBIDDEN_ENV.search(key) and (runtime[key] or key not in URL_SECRETS)} | {
        "EMAIL_PROVIDER_CONFIG_FILE", "STORAGE_CAPABILITIES_FILE", "ALLOWED_HOSTS",
        "PUBLIC_APP_BASE_URL", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS", "PLATFORM_STAFF_ORIGINS",
        "AWS_STORAGE_BUCKET_NAME", "AWS_S3_ENDPOINT_URL", "AWS_S3_PUBLIC_ENDPOINT_URL",
        "PUBLIC_IMAGE_BUCKET", "PUBLIC_IMAGE_BASE_URL", "EMAIL_HOST", "DEFAULT_FROM_EMAIL",
    }
    group = "spaceworks-saas-runtime" if saas else "spaceworks-runtime"
    variables = [{"key": key, **({"sync": False} if key in prompts else {"value": value})} for key, value in sorted(runtime.items())]
    if saas:
        variables += [{"key": key, "sync": False} for key in ("PLATFORM_DOMAIN_SUFFIX", "PLATFORM_ORIGIN_HOST")]
    roles = ["web"]
    if answers["profile"] == "full":
        roles.extend(["worker", "beat" if answers["task_profile"] == "redis" else "scheduler"])
    services = []
    for role in roles:
        service = {
            "type": "web" if role == "web" else "worker", "name": "spaceworks-" + role,
            "runtime": "image", "image": {"url": answers["backend_image"]},
            "plan": "free" if answers["profile"] == "free" else "0.5c-512mb",
            "dockerCommand": " ".join(command(role)), "envVars": [{"fromGroup": group}],
            "autoDeployTrigger": "off", "numInstances": 1,
        }
        if role == "web":
            service["healthCheckPath"] = "/api/v1/health/readiness/"
        services.append(service)
    return {"envVarGroups": [{"name": group, "envVars": variables}], "services": services}


def serialize_blueprint(value):
    # JSON flow objects are YAML 1.2, with one entry per line for reviewability.
    lines = ["# Generated role contract; run the separate finite release before enabling services.",
             "# Upload private rendered runtime settings; maintenance credentials belong only to release.",
             "# Secret JSON mounts must be uploaded as provider secret files at their configured paths.",
             "# The zero digest in the checked template MUST be replaced by one verified same-build digest.", "envVarGroups:"]
    for group in value["envVarGroups"]:
        lines += [f"  - name: {group['name']}", "    envVars:"]
        lines.extend("      - " + json.dumps(item) for item in group["envVars"])
    lines.append("services:")
    for service in value["services"]:
        lines.append("  - " + json.dumps(service))
    return "\n".join(lines) + "\n"


def render_native(directory, values, answers):
    root = Path(directory) / "rendered"
    if answers["provider"] == "render":
        write_private(root / "render.yaml", serialize_blueprint(render_blueprint(values, answers)))
    # All other checked provider examples are parameterized immutable-image
    # manifests with a role-specific private environment contract, not account APIs.
    source = Path(__file__).resolve().parents[2] / "deploy"
    from .native import render_provider
    render_provider(root, source, values, answers)
    if answers["provider"] == "kubernetes":
        from .kubernetes import render_kubernetes
        render_kubernetes(root, values, answers)
