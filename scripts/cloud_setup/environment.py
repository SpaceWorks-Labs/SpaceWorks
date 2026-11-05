"""One role-based effective environment, shared by every recipe renderer."""

from .errors import SetupError
from .free_profile import free_environment
from .secrets import RELEASE_ONLY

COMMON = {
    "SPACEWORKS_DEPLOYMENT_MODE": "managed", "DEBUG": "False", "MANAGED_POSTGRES": "True",
    "CONN_MAX_AGE": "60", "CONN_HEALTH_CHECKS": "True", "DISABLE_SERVER_SIDE_CURSORS": "False",
    "ENABLE_HTTPS": "true", "TRUST_X_FORWARDED_PROTO": "true", "TRUSTED_PROXY_COUNT": "1",
    "BEHIND_TRUSTED_PROXY": "False", "CONTROL_PLANE_PROXY": "false",
    "PII_ENCRYPTION_ENABLED": "False", "PII_ENCRYPTION_DUAL_READ": "True", "PII_KEY_BROKER": "local",
    "PII_DEK_CACHE_TTL_SECONDS": "300", "CRON_INTERVAL_SECONDS": "60", "PORT": "8000",
    "EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS": "2555", "EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS": "30",
    "EVENT_REIMBURSEMENT_FILE_MAX_BYTES": "10485760", "EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES": "104857600",
    "EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES": "1073741824", "EVENT_STAGE_FILE_RETENTION_DAYS": "365",
    "MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS": "0",
}
# Non-secret release-1 messaging and release-2 operator settings at their settings.py
# defaults, so every rendered recipe lists them and an operator may override each one
# (#194). Their secrets (TURNSTILE_SECRET_KEY, WEB_PUSH_VAPID_PRIVATE_KEY) stay in the
# protected secrets file, never here.
OPERATOR_DEFAULTS = {
    "NOTIFICATION_SLACK_REDIRECT_URI": "", "NOTIFICATION_MATTERMOST_REDIRECT_URI": "",
    "NOTIFICATION_DISCORD_REDIRECT_URI": "", "NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS": "False",
    "WHATSAPP_META_GRAPH_VERSION": "v25.0", "MESSAGING_WEBHOOK_BASE_URL": "",
    "TURNSTILE_SITE_KEY": "", "TURNSTILE_FAIL_MODE": "open", "TURNSTILE_HOSTNAMES": "",
    "LOGIN_IP_BLOCK_ENABLED": "True", "PASSWORD_BREACH_CHECK_ENABLED": "True", "WEBAUTHN_RP_NAME": "Space Works",
    "WEB_PUSH_VAPID_SUBJECT": "", "MIN_NATIVE_APP_VERSION_IOS": "", "MIN_NATIVE_APP_VERSION_ANDROID": "",
    "CARD_FONT_DOWNLOADS_ENABLED": "True",
    # #187A: the managed-hosting limiter and its online billing stay off unless the operator opts in.
    "MANAGED_PLANS_ENABLED": "False", "MANAGED_BILLING_ONLINE_ENABLED": "False",
}
COMMON.update(OPERATOR_DEFAULTS)
BOOLEAN_DEFAULTS = {
    "PII_ENCRYPTION_ENABLED", "PII_ENCRYPTION_DUAL_READ", "CONN_HEALTH_CHECKS", "DISABLE_SERVER_SIDE_CURSORS",
    "NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS", "LOGIN_IP_BLOCK_ENABLED", "PASSWORD_BREACH_CHECK_ENABLED",
    "CARD_FONT_DOWNLOADS_ENABLED", "MANAGED_PLANS_ENABLED", "MANAGED_BILLING_ONLINE_ENABLED",
}
SECRET_MOUNTS = {"EMAIL_PROVIDER_CONFIG_FILE", "STORAGE_CAPABILITIES_FILE"}
CONFIGURABLE_DEFAULTS = {
    "PII_ENCRYPTION_ENABLED", "PII_ENCRYPTION_DUAL_READ", "PII_KEY_BROKER", "PII_DEK_CACHE_TTL_SECONDS",
    "CONN_MAX_AGE", "CONN_HEALTH_CHECKS", "DISABLE_SERVER_SIDE_CURSORS", "CRON_INTERVAL_SECONDS",
    *(key for key in COMMON if key.startswith("EVENT_")), *OPERATOR_DEFAULTS,
}


def validate_default_override(name, value):
    if name in BOOLEAN_DEFAULTS:
        valid = value.lower() in {"true", "false"}
    elif name == "TURNSTILE_FAIL_MODE":
        valid = value in {"open", "closed"}
    elif name in OPERATOR_DEFAULTS:
        valid = True  # bounded single-line strings, already checked with the answers
    elif name == "PII_KEY_BROKER":
        valid = value in {"local", "aws_kms"}
    else:
        try:
            maximum = 60 if name == "CRON_INTERVAL_SECONDS" else 2**63 - 1
            valid = (0 if name == "CONN_MAX_AGE" else 1) <= int(value) <= maximum
        except ValueError:
            valid = False
    if not valid:
        raise SetupError("invalid_environment_setting", f"Supply a valid bounded {name}; full scheduler intervals cannot exceed 60 seconds.")


def effective_environment(answers, secrets):
    free = answers["profile"] == "free"
    values = dict(COMMON)
    values.update({
        "SPACEWORKS_DEPLOYMENT_PROFILE": answers["profile"],
        "DATABASE_CONNECTION_MODE": answers["database_connection_mode"],
        "ALLOWED_HOSTS": ",".join(answers["allowed_hosts"]),
        "INFRA_HOSTS": ",".join(answers["allowed_hosts"]),
        "TRUSTED_PROXY_COUNT": str(answers["trusted_proxy_count"]),
        "TRUST_X_FORWARDED_PROTO": "true" if answers["trusted_proxy_count"] else "false",
        "PUBLIC_APP_BASE_URL": answers["public_origin"].rstrip("/"),
        "CORS_ALLOWED_ORIGINS": answers["public_origin"].rstrip("/"),
        "CSRF_TRUSTED_ORIGINS": answers["public_origin"].rstrip("/"),
        "PLATFORM_STAFF_ORIGINS": answers["public_origin"].rstrip("/"),
        "EMAIL_PROVIDER": answers["email_provider"], "DEFAULT_FROM_EMAIL": answers["from_email"],
        "STORAGE_PRESIGN_METHOD": answers["presign_method"],
        "STORAGE_CAPABILITIES_FILE": answers["storage_capabilities_file"],
        "UPLOAD_SCAN_POLICY": "clamav" if answers["scan_policy"] == "external" else "none", "CLOUD_TASK_PROFILE": answers["task_profile"],
        "CLOUD_SCHEDULER": "beat" if answers["task_profile"] == "redis" else "loop",
        "CELERY_TASK_ALWAYS_EAGER": "False" if answers["task_profile"] == "redis" else "True",
    })
    if answers["provider"] == "cloud-run" and answers["task_profile"] == "brokerless":
        values["CLOUD_SCHEDULER"] = "external"
    values["SPACEWORKS_SECRET_FILE_MODE"] = "inline" if answers["provider"] in {"digitalocean", "koyeb", "railway", "cloud-run"} else "native"
    if answers["task_profile"] == "brokerless":
        values.update(CELERY_BROKER_URL="", CACHE_URL="", LIVE_REDIS_URL="")
    if free:
        values.update(free_environment(answers))
    for key, value in answers.get("environment", {}).items():
        if key in CONFIGURABLE_DEFAULTS:
            validate_default_override(key, value)
        elif key in values and values[key] != value:
            raise SetupError("environment_conflict", f"Remove the contradictory override for {key}.")
        if key in RELEASE_ONLY or key.startswith("SPACEWORKS_HOST") or key.startswith("BACKUP_OPS"):
            raise SetupError("host_authority_refused", "Managed recipes cannot carry host authority or maintenance overrides.")
        values[key] = value
    for key, value in secrets.items():
        if key in values and values[key] != value:
            raise SetupError("secret_environment_conflict", f"Remove the contradictory secret override for {key}.")
        if free and key in {"CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL", "CELERY_RESULT_BACKEND"} and value:
            raise SetupError("free_resident_service", "Free cannot use Redis, a live process or a resident scheduler.")
        if key.startswith("SPACEWORKS_HOST") or key == "BACKUP_OPS_DIR":
            raise SetupError("managed_host_authority", "Remove host authority from managed configuration.")
        values[key] = value
    if values.get("TRUST_FORWARDED_HOST", "false").lower() in {"true", "1", "yes", "on"}:
        if not all(values.get(name) for name in ("TRUSTED_EDGE_INGRESS_SECRET", "TRUSTED_EDGE_CIDRS", "TRUSTED_EDGE_UPSTREAM_HOSTS")):
            raise SetupError("edge_trust_incomplete", "Configure the protected edge secret, exact socket CIDRs and raw upstream hosts together.")
    values["DATABASE_MAINTENANCE_CONNECTION_MODE"] = answers["maintenance_connection_mode"]
    for endpoint in ("AWS_S3_ENDPOINT_URL", "AWS_S3_PUBLIC_ENDPOINT_URL", "PUBLIC_IMAGE_BASE_URL"):
        if values.get(endpoint):
            from .answers import https_url
            https_url(values[endpoint], endpoint)
    if "setup" in answers:
        for field, name in {
            "username": "SETUP_SUPERADMIN_USERNAME", "email": "SETUP_SUPERADMIN_EMAIL",
            "makerspace_name": "SETUP_MAKERSPACE_NAME", "makerspace_slug": "SETUP_MAKERSPACE_SLUG",
            "organization_name": "SETUP_ORGANIZATION_NAME", "module_profile": "SETUP_MODULE_PROFILE",
        }.items():
            values[name] = answers["setup"][field]
    return values


def role_environment(values, role):
    if role == "release":
        return dict(values)
    return {name: value for name, value in values.items() if name not in RELEASE_ONLY and not name.startswith("SETUP_")}


def command(role):
    process = {"web": "backend", "worker": "worker", "beat": "beat", "scheduler": "cron", "release": "migrate", "live": "backend"}[role]
    return ["--role", process, "python", "-m", "scripts.run_cloud_role", role]
