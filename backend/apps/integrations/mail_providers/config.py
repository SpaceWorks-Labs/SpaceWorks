"""Allowlisted, credential-only provider configuration; never an arbitrary URL/backend."""

from django.utils.translation import gettext
import json
import re
from dataclasses import dataclass, field
from email.utils import parseaddr

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

PROVIDERS = ("smtp", "resend", "postmark", "ses", "brevo", "mailgun", "sendgrid")
BACKENDS = {name: f"anymail.backends.{name}.EmailBackend" for name in PROVIDERS}
BACKENDS.update(smtp="apps.integrations.mail_providers.smtp_guarded.EmailBackend",
                ses="apps.integrations.mail_providers.ses.EmailBackend",
                resend="apps.integrations.mail_providers.resend.EmailBackend",
                sendgrid="apps.integrations.mail_providers.sendgrid.EmailBackend")
KEYS = {
    "smtp": set(), "resend": {"api_key"}, "brevo": {"api_key"},
    "sendgrid": {"api_key"}, "postmark": {"server_token"},
    "mailgun": {"api_key", "domain", "region"},
    "ses": {"region", "access_key_id", "secret_access_key", "session_token", "workload_identity"},
}
KEYS["resend"].add("webhook_secret")
KEYS["mailgun"].add("webhook_signing_key")


@dataclass(frozen=True)
class MailConfig:
    provider: str
    sender: str
    credentials: dict = field(default_factory=dict, repr=False)
    account_key: str = ""


def validate_config(provider, values, sender):
    if provider not in PROVIDERS:
        raise ValidationError(gettext("Select a supported email provider."))
    if not isinstance(values, dict) or set(values) - KEYS[provider] - {"account_key"}:
        raise ValidationError(gettext("Unsupported email provider fields."))
    values = dict(values)
    account = values.pop("account_key", "")
    if not isinstance(account, str) or (account and not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", account)):
        raise ValidationError(gettext("Invalid email account key."))
    for key, value in values.items():
        if key == "workload_identity":
            if not isinstance(value, bool):
                raise ValidationError(gettext("Workload identity must be a boolean."))
        elif not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
            raise ValidationError(gettext("Invalid email provider credential."))
    if not isinstance(sender, str) or "\r" in sender or "\n" in sender:
        raise ValidationError(gettext("Enter a valid sender email address."))
    validate_email(parseaddr(sender)[1])
    required = {"postmark": {"server_token"}, "mailgun": {"api_key", "domain", "region"},
                "ses": {"region"}, "smtp": set()}.get(provider, {"api_key"})
    if not required <= values.keys():
        raise ValidationError(gettext("Required email provider credentials are missing."))
    if provider == "mailgun":
        labels = values["domain"].split(".")
        if values["region"] not in {"us", "eu"} or len(values["domain"]) > 253 or len(labels) < 2 or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels):
            raise ValidationError(gettext("Enter a Mailgun domain and US or EU region."))
    if provider == "ses":
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", values["region"]):
            raise ValidationError(gettext("Enter a valid SES region."))
        pair = {"access_key_id", "secret_access_key"} & values.keys()
        if values.get("workload_identity"):
            if pair or values.get("session_token"):
                raise ValidationError(gettext("Select dedicated credentials or workload identity."))
        elif len(pair) != 2:
            raise ValidationError(gettext("Dedicated SES credentials are required."))
    return MailConfig(provider, sender, values, account)


def encode_config(values):
    """For model setters only; never include this output in a response or audit."""
    if not isinstance(values, dict):
        raise ValidationError(gettext("Provider configuration must be an object."))
    return json.dumps(values, separators=(",", ":"), sort_keys=True)
