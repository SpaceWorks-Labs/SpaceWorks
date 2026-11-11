"""Provider rendering installs the same role environment in every consumer."""

import json
from pathlib import Path, PurePosixPath

from .answers import FORBIDDEN_ENV
from .environment import command, role_environment
from .errors import SetupError
from .private_files import write_private
from .recipes import IMAGE_PLACEHOLDER


def secret_name(name):
    return "spaceworks-" + name.lower().replace("_", "-")


def cloud_run(document, values, answers):
    kind = document.get("kind")
    if kind not in {"Job", "Service", "WorkerPool"}:
        # Scheduler HTTP target is a provider API request, not a Cloud Run object.
        if "httpTarget" in document and answers["profile"] == "free":
            from .free_profile import tick_cron
            document["httpTarget"]["uri"] = answers["api_origin"].rstrip("/") + "/api/v1/internal/free/tick"
            document["httpTarget"]["oidcToken"]["audience"] = answers["api_origin"].rstrip("/")
            document["httpTarget"]["headers"]["X-Cron-Secret"] = values["FREE_TICK_SECRET"]
            document["schedule"] = tick_cron(int(values["FREE_TICK_INTERVAL_SECONDS"]))
        return document
    spec = document["spec"]["template"]["spec"]
    if kind == "Job":
        spec = spec["template"]["spec"]
    container = spec["containers"][0]
    role = "release" if container["args"][-1] == "release" else "web"
    if kind == "WorkerPool" and answers["task_profile"] != "redis":
        raise SetupError("worker_pool_profile", "Cloud Run worker pools are the Redis alternative; brokerless uses bounded work Jobs.")
    container["image"] = answers["backend_image"]
    environment = role_environment(values, role)
    # Scheduler selection was derived once in effective_environment, which is
    # also hashed into the live acceptance receipt. Never change it here.
    container["env"] = []
    volumes, mounts, parents = [], [], set()
    for key, value in sorted(environment.items()):
        if key in {"EMAIL_PROVIDER_CONFIG_FILE", "STORAGE_CAPABILITIES_FILE"} and values.get("SPACEWORKS_SECRET_FILE_MODE") != "inline":
            target = PurePosixPath(value)
            if not target.is_absolute() or ".." in target.parts or str(target.parent) in parents:
                raise SetupError("cloud_run_secret_mounts", "Use separate absolute parent directories for email/storage secret mounts on Cloud Run.")
            parents.add(str(target.parent))
            volume = secret_name(key)
            volumes.append({"name": volume, "secret": {"secretName": volume, "items": [{"key": "latest", "path": target.name}]}})
            mounts.append({"name": volume, "mountPath": str(target.parent)})
        item = {"name": key}
        if FORBIDDEN_ENV.search(key) and value:
            item["valueFrom"] = {"secretKeyRef": {"name": secret_name(key), "key": "latest"}}
        else:
            item["value"] = value
        container["env"].append(item)
    if volumes:
        spec["volumes"] = volumes
        container["volumeMounts"] = mounts
    return document


def digitalocean(document, values, answers):
    image, digest = answers["backend_image"].split("@", 1)
    registry, repository = image.removeprefix("ghcr.io/").split("/", 1)
    if not image.startswith("ghcr.io/"):
        raise SetupError("digitalocean_registry", "Select a GHCR image for this App Platform recipe, or configure a provider-supported registry explicitly.")
    for group in ("services", "workers", "jobs"):
        for service in document.get(group, []):
            role = service["name"]
            if role == "scheduler" and answers["task_profile"] == "redis":
                role = service["name"] = "beat"
            service["image"] = {"registry_type": "GHCR", "registry": registry, "repository": repository, "digest": digest}
            service["run_command"] = " ".join(command(role))
            service["envs"] = [{"key": key, "value": value, "scope": "RUN_TIME", **({"type": "SECRET"} if FORBIDDEN_ENV.search(key) else {})} for key, value in sorted(role_environment(values, role).items())]
    return document


def koyeb(document, values, answers):
    if "definition" not in document:
        return document
    definition = document["definition"]
    role = definition["name"].removeprefix("spaceworks-")
    if role == "scheduler" and answers["task_profile"] == "redis":
        role = "beat"
        definition["name"] = "spaceworks-beat"
    definition["docker"] = {"image": answers["backend_image"], "args": command(role)}
    definition["env"] = [{"key": key, **({"secret": secret_name(key)} if FORBIDDEN_ENV.search(key) and value else {"value": value})} for key, value in sorted(role_environment(values, role).items())]
    return document


def fly(text, path, values, answers):
    import tomllib
    parsed = tomllib.loads(text)
    role = path.stem.split(".")[-1]
    if role == "scheduler" and answers["task_profile"] == "redis":
        role = "beat"
    # Preserve the provider's reviewed network/resource sections. Only replace
    # [env] through [[vm]], plus the role invocation and immutable image.
    start, end = text.index("[env]"), text.index("[[vm]]")
    plain = {k: v for k, v in role_environment(values, role).items() if not FORBIDDEN_ENV.search(k) or not v}
    block = "[env]\n" + "".join(f"  {key} = {json.dumps(value)}\n" for key, value in sorted(plain.items()))
    text = text[:start] + block + text[end:]
    text = text.replace(IMAGE_PLACEHOLDER, answers["backend_image"])
    text = text.replace(parsed["processes"]["app"], " ".join(command(role)))
    text = text.split("\n[[files]]", 1)[0].rstrip() + "\n"
    from .secret_files import INLINE_FILES
    for name, inline in INLINE_FILES.items():
        if values.get(name):
            text += f'\n[[files]]\n  guest_path = {json.dumps(values[name])}\n  secret_name = {json.dumps(inline)}\n'
    return text


def render_provider(root, source, values, answers):
    provider = answers["provider"]
    selected = {"fly": "fly", "railway": "railway", "koyeb": "koyeb", "digitalocean": "digitalocean", "cloud-run": "cloud-run/free" if answers["profile"] == "free" else "cloud-run"}.get(provider)
    if not selected:
        return
    if provider in {"digitalocean", "koyeb", "railway", "cloud-run"}:
        from .secret_files import INLINE_FILES, read_config
        for name, inline in INLINE_FILES.items():
            if values.get(name) and not values.get(inline):
                raise SetupError("provider_secret_file_required", f"Supply {inline} in protected secrets and let the bootstrap step write it to a file (materialize_secret_files) before enabling this provider; a file-path setting alone cannot deliver a file.")
            if values.get(name):
                path = PurePosixPath(values[name])
                if not str(path).startswith("/tmp/spaceworks-secrets/") or ".." in path.parts:
                    raise SetupError("inline_secret_path", "Inline provider recipes require private file targets under /tmp/spaceworks-secrets/.")
                read_config(values, name)
    for path in (source / selected).iterdir():
        if not path.is_file() or path.suffix not in {".json", ".yaml", ".toml"}:
            continue
        if provider == "cloud-run":
            if path.name in {"worker.yaml", "beat.yaml"} and answers["task_profile"] != "redis":
                continue
            if path.name in {"scheduler-job.yaml", "scheduler.yaml", "work-job.yaml", "work-scheduler.yaml"} and answers["task_profile"] == "redis":
                continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".toml":
            text = fly(text, path, values, answers)
        else:
            document = json.loads(text)
            if provider == "cloud-run":
                document = cloud_run(document, values, answers)
            elif provider == "digitalocean":
                document = digitalocean(document, values, answers)
            elif provider == "koyeb":
                document = koyeb(document, values, answers)
            text = json.dumps(document, indent=2).replace(IMAGE_PLACEHOLDER, answers["backend_image"]) +"\n"
        write_private(root / path.name, text)
