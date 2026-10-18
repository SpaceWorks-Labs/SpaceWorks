"""Optional cloud settings, with all resource limits inside the free branch."""
from django.core.exceptions import ImproperlyConfigured


def storage_proof_ttl(env, selection):
    minimum = 60
    default = 900
    if selection.is_free:
        # Each free tick refreshes at most one binding. Allow a complete cycle,
        # one missed/cold-start tick and the final tick's execution budget.
        bindings = 2
        path = env("STORAGE_CAPABILITIES_FILE", default="")
        if path:
            from apps.storage_capabilities.configuration import read_configuration

            bindings = len(read_configuration(path))
        interval = env.int("FREE_TICK_INTERVAL_SECONDS", default=600)
        budget = env.int("FREE_TICK_BUDGET_SECONDS", default=20)
        # A completed cycle is due again after five minutes. Round that wait up
        # to actual trigger slots when a custom cadence is faster than the task.
        due_ticks = (300 + interval - 1) // interval
        minimum = (bindings + max(1, due_ticks)) * interval + budget
        default = max(default, minimum)
    ttl = env.int("STORAGE_CAPABILITY_TTL_SECONDS", default=default)
    if not minimum <= ttl <= 86400:
        raise ImproperlyConfigured(
            f"Storage proof TTL must be in {minimum}..86400 seconds; "
            "free cadence must cover every binding plus one tick of headroom."
        )
    return ttl


def deployment_settings(env, selection):
    values = {
        "STORAGE_CAPABILITIES_FILE": env("STORAGE_CAPABILITIES_FILE", default=""),
        "STORAGE_CAPABILITY_TTL_SECONDS": storage_proof_ttl(env, selection),
        "AWS_SESSION_TOKEN": env("AWS_SESSION_TOKEN", default=""),
        "TRUST_FORWARDED_HOST": env.bool("TRUST_FORWARDED_HOST", default=False),
        "TRUSTED_EDGE_INGRESS_SECRET": env("TRUSTED_EDGE_INGRESS_SECRET", default=""),
        "TRUSTED_EDGE_CIDRS": env.list("TRUSTED_EDGE_CIDRS", default=[]),
        "TRUSTED_EDGE_UPSTREAM_HOSTS": env.list("TRUSTED_EDGE_UPSTREAM_HOSTS", default=[]),
        # Incoming programmes must be reviewed before their tasks can be selected.
        "CLOUD_PROGRAMMES": (),
    }
    if selection.mode == "managed" and "*" in env.list("ALLOWED_HOSTS", default=[]):
        raise ImproperlyConfigured("Managed ingress requires explicit allowed hosts.")
    if selection.mode == "managed":
        values["MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS"] = env.int("MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS", default=0)
        if not 0 <= values["MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS"] <= 86400:
            raise ImproperlyConfigured("Managed transfer horizon must be in 0..86400 seconds.")
    if values["TRUST_FORWARDED_HOST"]:
        if (selection.mode != "managed" or not values["TRUSTED_EDGE_CIDRS"]
                or not values["TRUSTED_EDGE_UPSTREAM_HOSTS"]
                or env.int("TRUSTED_PROXY_COUNT", default=0) < 1):
            raise ImproperlyConfigured("Forwarded hosts require explicit managed ingress and proxy count.")
        secret = values["TRUSTED_EDGE_INGRESS_SECRET"]
        if not isinstance(secret, str) or not 32 <= len(secret) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in secret):
            raise ImproperlyConfigured("Trusted edge ingress requires a protected 32..256 byte secret.")
        if not env.bool("TRUST_X_FORWARDED_PROTO", default=False):
            raise ImproperlyConfigured("Forwarded hosts require explicit trusted HTTPS forwarding.")
        values["USE_X_FORWARDED_HOST"] = True
    policy = env("UPLOAD_SCAN_POLICY", default="none" if selection.mode == "managed" else "")
    if policy:
        if policy not in {"none", "clamav"}:
            raise ImproperlyConfigured("Select none or clamav scanning.")
        values["UPLOAD_SCAN_POLICY"] = policy
        if policy == "clamav":
            values.update(CLAMD_HOST=env("CLAMD_HOST", default=""),
                CLAMD_PORT=env.int("CLAMD_PORT", default=3310),
                CLAMD_TIMEOUT_SECONDS=env.int("CLAMD_TIMEOUT_SECONDS", default=5),
                CLAMD_MAX_SCAN_BYTES=env.int("CLAMD_MAX_SCAN_BYTES", default=2147483648))
            if (not values["CLAMD_HOST"] or not 1 <= values["CLAMD_PORT"] <= 65535
                    or not 1 <= values["CLAMD_TIMEOUT_SECONDS"] <= 60
                    or values["CLAMD_MAX_SCAN_BYTES"] < 1):
                raise ImproperlyConfigured("ClamAV requires an explicit host and valid bounded scan limits.")
    if selection.is_free:
        values.update({
            "FREE_EMAIL_ACCOUNT_KEY": env("FREE_EMAIL_ACCOUNT_KEY", default=""),
            "FREE_EMAIL_PROVIDER": env("FREE_EMAIL_PROVIDER", default=""),
            "FREE_EMAIL_MONTHLY_CAP": env.int("FREE_EMAIL_MONTHLY_CAP", default=None),
            "FREE_EMAIL_RESET_TIMEZONE": env("FREE_EMAIL_RESET_TIMEZONE", default="UTC"),
            "FREE_EMAIL_ACCOUNTS": env.json("FREE_EMAIL_ACCOUNTS", default={}),
            "FREE_TICK_INGRESS_LIMIT_PER_MINUTE": env.int("FREE_TICK_INGRESS_LIMIT_PER_MINUTE", default=120),
            "FREE_MAX_PROMOTION_BYTES": env.int("FREE_MAX_PROMOTION_BYTES", default=16777216),
        })
        if not 1 <= values["FREE_MAX_PROMOTION_BYTES"] <= 16777216:
            raise ImproperlyConfigured("Free promotion limit must be in 1..16777216 bytes.")
        monthly = values["FREE_EMAIL_MONTHLY_CAP"]
        if monthly is not None and monthly < 1:
            raise ImproperlyConfigured("Monthly mail cap must be positive.")
    return values
