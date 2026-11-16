"""Setup-time allowlist for HTTP provider secret mounts; no dynamic backends."""

import re

from .errors import SetupError

FIELDS = {
    "resend": ({"api_key"}, set()), "brevo": ({"api_key"}, set()),
    "sendgrid": ({"api_key"}, set()), "postmark": ({"server_token"}, set()),
    "mailgun": ({"api_key", "domain"}, {"region"}),
    "ses": ({"region"}, {"access_key_id", "secret_access_key", "session_token"}),
}


def validate_config(provider, value):
    required, optional = FIELDS[provider]
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise SetupError("mail_provider_fields", "Use only the selected provider's typed credential fields; custom API URLs/backends are refused.")
    for item in value.values():
        if not isinstance(item, str) or not item or len(item) > 8192 or any(c in item for c in "\x00\r\n"):
            raise SetupError("mail_provider_value", "Supply bounded nonempty provider values in the protected mail config file.")
    if provider == "mailgun":
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+", value["domain"]) or value.get("region", "us") not in {"us", "eu"}:
            raise SetupError("mailgun_configuration", "Supply a verified Mailgun domain and the explicit us/eu region.")
    if provider == "ses":
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", value["region"]):
            raise SetupError("ses_region", "Supply a supported SES region, never a caller-selected API base URL.")
        if bool(value.get("access_key_id")) != bool(value.get("secret_access_key")):
            raise SetupError("ses_credentials", "Supply both dedicated SES credentials or use its separately scoped workload identity; never inherit R2 credentials.")
    return {"provider": provider, "status": "configured"}
