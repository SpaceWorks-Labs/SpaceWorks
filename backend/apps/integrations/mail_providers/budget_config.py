"""Free-only account budgets; tenant quotas remain independent."""

import re
import hashlib
import json
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def free_profile():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"


@dataclass(frozen=True)
class AccountBudget:
    key: str
    provider: str
    daily_cap: int
    monthly_cap: int | None
    reset_timezone: str


def credential_fingerprint(config):
    """Operator-only account binding; never expose this in health/API responses."""
    credentials = {k: v for k, v in config.credentials.items() if not k.startswith("webhook_")}
    return hashlib.sha256(json.dumps([config.provider, credentials],
                                   sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def account_budget(config):
    if config.provider == "smtp":
        raise ImproperlyConfigured("Free mail requires an HTTP provider account.")
    key = config.account_key or getattr(settings, "FREE_EMAIL_ACCOUNT_KEY", "")
    accounts = getattr(settings, "FREE_EMAIL_ACCOUNTS", {})
    if not isinstance(accounts, dict):
        raise ImproperlyConfigured("Invalid free email accounts.")
    values = accounts.get(key)
    if values is None and key == getattr(settings, "FREE_EMAIL_ACCOUNT_KEY", ""):
        values = {"provider": getattr(settings, "FREE_EMAIL_PROVIDER", "") or getattr(settings, "EMAIL_PROVIDER", ""),
                  "daily_cap": getattr(settings, "FREE_EMAIL_DAILY_CAP", None),
                  "monthly_cap": getattr(settings, "FREE_EMAIL_MONTHLY_CAP", None),
                  "reset_timezone": getattr(settings, "FREE_EMAIL_RESET_TIMEZONE", "UTC")}
    if not isinstance(values, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
        raise ImproperlyConfigured("Free email account is not configured.")
    if values.get("provider") != config.provider:
        raise ImproperlyConfigured("Free email account provider mismatch.")
    fingerprints = values.get("credential_fingerprints")
    if fingerprints is None and key == getattr(settings, "FREE_EMAIL_ACCOUNT_KEY", ""):
        # The default account belongs to the selected platform transport. A tenant
        # cannot spend its allowance with unrelated credentials by omitting a key.
        from apps.integrations.models_email import PlatformEmailSettings
        from .selection import environment_config, stored_config
        platform = stored_config(PlatformEmailSettings.load()) or environment_config()
        fingerprints = [credential_fingerprint(platform)] if platform else []
    if not isinstance(fingerprints, list) or credential_fingerprint(config) not in fingerprints:
        raise ImproperlyConfigured("Free email account credential scope mismatch.")
    daily, monthly = values.get("daily_cap"), values.get("monthly_cap")
    if type(daily) is not int or not 0 < daily <= 10_000_000:
        raise ImproperlyConfigured("A positive free daily email cap is required.")
    if monthly is not None and (type(monthly) is not int or not 0 < monthly <= 100_000_000):
        raise ImproperlyConfigured("Invalid free monthly email cap.")
    zone = values.get("reset_timezone", "UTC")
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise ImproperlyConfigured("Invalid email provider reset timezone.") from None
    return AccountBudget(key, config.provider, daily, monthly, zone)
