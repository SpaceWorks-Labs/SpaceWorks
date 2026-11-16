"""Query-free startup checks registered by G's EncryptionConfig integration."""

import base64

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, register

from apps.encryption.account_registry import all_fields


@register()
def check_account_pii_configuration(app_configs=None, **kwargs):
    if not getattr(settings, "ACCOUNT_SAVED_DETAILS_ENABLED", False):
        return []
    errors = []
    broker = getattr(settings, "ACCOUNT_PII_KEY_BROKER", "local")
    if broker == "local":
        from apps.encryption.brokers.local import BinaryFernet

        try:
            master = getattr(settings, "ACCOUNT_PII_MASTER_KEY", "")
            BinaryFernet(master)
            raw = base64.urlsafe_b64decode(master.encode() if isinstance(master, str) else master)
            for name in ("PII_MASTER_KEY", "PII_SEARCH_HASH_KEY", "AUDIT_MAC_MASTER_KEY",
                         "PUSH_TOKEN_HMAC_KEY", "SECRET_KEY"):
                other = getattr(settings, name, "")
                if other == master:
                    raise ValueError("Shared secret")
                try:
                    other_raw = base64.urlsafe_b64decode(other.encode() if isinstance(other, str) else other)
                except Exception:
                    continue
                if raw == other_raw:
                    raise ValueError("Shared secret")
            previous = getattr(settings, "ACCOUNT_PII_MASTER_KEY_PREVIOUS", "")
            if previous:
                BinaryFernet(previous)
        except Exception:
            errors.append(Error("Account saved details require an independent 32-byte local wrapping key.",
                                hint="Configure and persist ACCOUNT_PII_MASTER_KEY; never regenerate it on boot.",
                                id="encryption.E101"))
    elif broker == "aws_kms":
        if not getattr(settings, "ACCOUNT_PII_AWS_KMS_KEY_ID", ""):
            errors.append(Error("Account KMS broker requires ACCOUNT_PII_AWS_KMS_KEY_ID.", id="encryption.E102"))
        try:
            import boto3  # noqa: F401
        except ImportError:
            errors.append(Error("Account KMS broker requires boto3.", id="encryption.E103"))
    else:
        errors.append(Error("ACCOUNT_PII_KEY_BROKER must be local or aws_kms.", id="encryption.E104"))
    return errors


@register()
def check_account_pii_registration(app_configs=None, **kwargs):
    from apps.encryption.account_mappers import AccountPiiModelMixin

    declared = {(item.model_label, item.field_name) for item in all_fields()}
    errors = []
    if getattr(settings, "ACCOUNT_SAVED_DETAILS_ENABLED", False):
        for label, name in sorted(declared):
            try:
                model = apps.get_model(label)
                model._meta.get_field(name)
                valid = issubclass(model, AccountPiiModelMixin)
            except Exception:
                # Keep startup diagnostics actionable without exposing data.
                valid = False
            if not valid:
                errors.append(Error(f"{label}.{name} is missing its account encryption mapper.",
                                    id="encryption.E106"))
    for model in apps.get_models():
        if not issubclass(model, AccountPiiModelMixin):
            continue
        fields = [name for label, name in declared if label == model._meta.label]
        if not fields or any(name not in {field.name for field in model._meta.fields} for name in fields):
            errors.append(Error(f"{model._meta.label} has no valid account PII registration.", id="encryption.E105"))
    return errors
