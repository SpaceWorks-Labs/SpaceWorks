"""Generate private existingSecret inputs; no kubectl or cluster mutation."""

import json

from .environment import role_environment
from .private_files import write_json


def render_kubernetes(root, values, answers):
    runtime = role_environment(values, "web")
    release = {key: value for key, value in values.items() if key not in runtime}
    for role, content in (("runtime", runtime), ("release", release)):
        write_json(root / f"secret.{role}.json", {
            "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
            "metadata": {"name": f"spaceworks-{role}"}, "stringData": content,
        })
    image, digest = answers["backend_image"].split("@", 1)
    chart = {
        "deploymentMode": "managed", "deploymentProfile": "full",
        "backendImage": image, "backendDigest": digest,
        "runtimeSecret": "spaceworks-runtime", "releaseSecret": "spaceworks-release",
        "rolloutGeneration": values["SPACEWORKS_DEPLOYMENT_ID"],
        "taskProfile": answers["task_profile"], "scheduler": values["CLOUD_SCHEDULER"],
        "beat": {"enabled": answers["task_profile"] == "redis", "existingClaim": "REPLACE_OWNED_BEAT_PVC" if answers["task_profile"] == "redis" else ""},
        "frontend": {"enabled": "frontend_image" in answers}, "configFiles": [],
        "live": {"enabled": False},
        "resources": {"requests": {"cpu": "100m", "memory": "512Mi"}, "limits": {"memory": "1Gi"}},
    }
    if "frontend_image" in answers:
        chart["frontendImage"], chart["frontendDigest"] = answers["frontend_image"].split("@", 1)
    for key, name in (("STORAGE_CAPABILITIES_FILE", "storage-capabilities"), ("EMAIL_PROVIDER_CONFIG_FILE", "email-provider")):
        if values.get(key):
            chart["configFiles"].append({"name": name, "secretName": "spaceworks-" + name, "key": "config.json", "mountPath": values[key]})
    # A YAML 1.2 document may use JSON syntax. These values are private; rendered
    # Secret manifests must never be committed or attached to CI logs/artifacts.
    write_json(root / "values.yaml", chart)
