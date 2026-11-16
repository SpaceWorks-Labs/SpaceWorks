"""Version-1 setup input: closed fields, no credential arguments or shell syntax."""

import re
from urllib.parse import urlsplit

from .errors import SetupError

PROVIDERS = {"render", "railway", "fly", "koyeb", "digitalocean", "cloud-run", "docker", "kubernetes", "northflank"}
EMAIL_PROVIDERS = {"smtp", "resend", "postmark", "ses", "brevo", "mailgun", "sendgrid"}
REQUIRED = {
    "version", "provider", "profile", "backend_image", "database_provider",
    "database_connection_mode", "maintenance_connection_mode", "database_documentation_url",
    "connection_limit", "task_profile", "public_origin", "api_origin", "allowed_hosts", "trusted_proxy_count",
    "email_provider", "from_email", "presign_method", "scan_policy", "storage_capabilities_file",
}
OPTIONAL = {"free", "environment", "send_test_recipient", "setup", "frontend_image"}
URL_SECRETS = {"CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "CACHE_URL", "LIVE_REDIS_URL"}
FORBIDDEN_ENV = re.compile(r"PASSWORD|SECRET|TOKEN|PRIVATE_KEY|MASTER_KEY|SEARCH_HASH_KEY|ENC_KEY|PEPPER|DATABASE.*URL|ACCESS_KEY|CELERY_BROKER_URL|CELERY_RESULT_BACKEND|CACHE_URL|LIVE_REDIS_URL|SPACEWORKS_.*_B64", re.I)


def https_url(value, name, *, origin=False):
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        valid = valid and not parsed.fragment and not parsed.query and parsed.port in (None, 443)
        if origin:
            valid = valid and parsed.path in ("", "/")
        if not valid or any(c in value for c in "\r\n\x00"):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise SetupError("invalid_https_url", f"Supply an exact HTTPS URL for {name}, without credentials, query or fragment.") from None
    return value.rstrip("/") if origin else value


def validate_answers(value):
    if not isinstance(value, dict) or set(value) - REQUIRED - OPTIONAL or REQUIRED - set(value):
        raise SetupError("answer_fields", "Supply exactly the required version-1 choices; see deploy/cloud/answers.example.json.")
    if type(value["version"]) is not int or value["version"] != 1:
        raise SetupError("answer_version", "Use setup answer version 1.")
    choices = {
        "provider": PROVIDERS, "profile": {"full", "free"},
        "database_provider": {"supabase", "neon", "generic", "rds", "digitalocean", "aiven"},
        "database_connection_mode": {"direct", "session"}, "maintenance_connection_mode": {"direct", "session"},
        "task_profile": {"redis", "brokerless"}, "email_provider": EMAIL_PROVIDERS,
        "presign_method": {"put", "post"}, "scan_policy": {"none", "external"},
    }
    for key, allowed in choices.items():
        if not isinstance(value[key], str) or value[key] not in allowed:
            raise SetupError("invalid_choice", f"Select a supported {key}; transaction pooling is unsupported.")
    for field in ("backend_image", "frontend_image"):
        if field in value and (not isinstance(value[field], str) or not re.fullmatch(r"[a-zA-Z0-9./_-]+@sha256:[0-9a-f]{64}", value[field]) or value[field].endswith("0" * 64)):
            raise SetupError("immutable_image_required", f"Pin {field} to a verified OCI sha256 digest.")
    for key in ("public_origin", "api_origin"):
        https_url(value[key], key, origin=True)
    https_url(value["database_documentation_url"], "database_documentation_url")
    hosts = value["allowed_hosts"]
    if not isinstance(hosts, list) or not hosts or any(not isinstance(h, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", h) or ".." in h for h in hosts):
        raise SetupError("exact_hosts_required", "List exact infrastructure hosts; wildcards and leading-dot trust are refused.")
    if urlsplit(value["api_origin"]).hostname not in hosts:
        raise SetupError("api_host_missing", "Include the API origin host in allowed_hosts.")
    if type(value["trusted_proxy_count"]) is not int or not 0 <= value["trusted_proxy_count"] <= 8:
        raise SetupError("proxy_count", "Declare the exact validated ingress proxy count (0 through 8), including any static proxy.")
    if type(value["connection_limit"]) is not int or not 8 <= value["connection_limit"] <= 10000:
        raise SetupError("connection_budget", "Declare a DB connection allowance of at least eight, including guard/probe connections.")
    for key in ("from_email", "send_test_recipient"):
        if key in value and (not isinstance(value[key], str) or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", value[key])):
            raise SetupError("invalid_email", f"Supply one verified mailbox for {key}.")
    if not isinstance(value["storage_capabilities_file"], str) or not value["storage_capabilities_file"].startswith("/"):
        raise SetupError("capability_file", "Select an absolute private storage-capabilities secret-mount path.")
    if value["profile"] == "free":
        if value["provider"] not in {"render", "cloud-run", "docker", "northflank"}:
            raise SetupError("free_recipe_unqualified", "Use the separate Render/Cloud Run free recipe; Oracle uses the unchanged host/full installer.")
        if value["task_profile"] != "brokerless":
            raise SetupError("free_topology_conflict", "Free requires brokerless tasks and the external tick.")
        from .free_profile import free_environment
        free_environment(value)
    elif "free" in value:
        raise SetupError("full_free_settings", "Remove free choices from the full setup input; full defaults remain unchanged.")
    environment = value.get("environment", {})
    if not isinstance(environment, dict):
        raise SetupError("invalid_environment", "Supply environment as a string mapping.")
    for key, item in environment.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or FORBIDDEN_ENV.search(key):
            raise SetupError("secret_in_answers", "Put all credentials in the protected secrets file, never answers or argv.")
        if not isinstance(item, str) or len(item) > 8192 or any(c in item for c in "\x00\r\n"):
            raise SetupError("invalid_environment", "Use bounded single-line environment values.")
    if "setup" in value:
        setup = value["setup"]
        fields = {"username", "email", "makerspace_name", "makerspace_slug", "organization_name", "module_profile"}
        if not isinstance(setup, dict) or set(setup) != fields or any(not isinstance(v, str) or not v or len(v) > 150 or any(c in v for c in "\x00\r\n") for v in setup.values()):
            raise SetupError("setup_choices", "Supply all explicit account, organization and makerspace setup choices.")
        if not re.fullmatch(r"[A-Za-z0-9@.+_-]{1,150}", setup["username"]) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", setup["makerspace_slug"]):
            raise SetupError("setup_identity", "Use a valid username and lowercase makerspace slug.")
        if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", setup["email"]):
            raise SetupError("setup_email", "Supply the initial platform administrator's real mailbox.")
        if setup["module_profile"] not in {"minimal", "cloud", "full", "lending", "workshop", "recommended", "everything", "events", "bookings"}:
            raise SetupError("module_profile", "Select an existing module install profile; it is separate from the deployment profile.")
    return value
