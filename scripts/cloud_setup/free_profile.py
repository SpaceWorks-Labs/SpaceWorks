"""Explicit opt-in free topology and provider-account planning caps."""

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import SetupError

FREE_NOTICE = (
    "Free (best effort): one 512 MB web container; cold starts, missed ticks and quotas "
    "can delay requests and reminders. No SLA. Binary-dependent media is unavailable; "
    "malware scanning is off unless an external scanner is selected. No scheduled pg_dump. "
    "Verify ongoing account allowances, card requirements, spend controls and sender-domain "
    "ownership. A domain may cost extra. Provider backups may be unavailable. Daily external "
    "encrypted backup or qualified portable export needs separate object/key custody; "
    "ordinary tenant archives cannot be restored."
)

FREE_ENV = {
    "CLOUD_TASK_PROFILE": "brokerless", "CLOUD_SCHEDULER": "tick",
    "CELERY_BROKER_URL": "", "CELERY_RESULT_BACKEND": "",
    "CACHE_URL": "", "LIVE_REDIS_URL": "", "CELERY_TASK_ALWAYS_EAGER": "True",
    "GUNICORN_WORKERS": "1", "GUNICORN_THREADS": "1",
    "FREE_TICK_INTERVAL_SECONDS": "600", "FREE_TICK_BUDGET_SECONDS": "20",
    "FREE_TICK_RATE_LIMIT_PER_MINUTE": "6",
}


def positive(value, name, maximum=2**63 - 1):
    if type(value) is not int or not 1 <= value <= maximum:
        raise SetupError("invalid_cap", f"Supply a positive bounded integer for {name}.")
    return str(value)


def tick_cron(interval):
    if interval <= 3600 and interval % 60 == 0 and 3600 % interval == 0:
        return f"*/{interval // 60} * * * *" if interval < 3600 else "0 * * * *"
    if interval % 3600 == 0 and 86400 % interval == 0:
        return f"0 */{interval // 3600} * * *" if interval < 86400 else "0 0 * * *"
    raise SetupError("free_cron_interval", "Use an exact minute/hour divisor supported by the external cron schedule (for example 600, 1800 or 3600 seconds).")


def free_environment(answers):
    caps = answers.get("free")
    required = {
        "db_cap_bytes", "object_cap_bytes", "email_daily_cap", "email_monthly_cap",
        "email_account_key", "email_reset_timezone", "source_url", "checked_on",
        "acknowledge_limits", "tick_interval_seconds",
    }
    if not isinstance(caps, dict) or set(caps) != required or caps["acknowledge_limits"] is not True:
        raise SetupError("free_caps_required", "Confirm the free limitations and supply every version-1 free cap/source field.")
    from .answers import https_url
    https_url(caps["source_url"], "free.source_url")
    try:
        checked = date.fromisoformat(caps["checked_on"])
        if not 0 <= (date.today() - checked).days <= 31:
            raise ValueError
        if caps["email_reset_timezone"] != "UTC":
            ZoneInfo(caps["email_reset_timezone"])
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise SetupError("stale_cap_source", "Verify allowances within 31 days and supply a valid IANA reset timezone.") from None
    import re
    if not isinstance(caps["email_account_key"], str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", caps["email_account_key"]):
        raise SetupError("invalid_mail_account", "Use a stable non-secret account budget key shared by all senders on that provider account.")
    interval = int(positive(caps["tick_interval_seconds"], "tick_interval_seconds", 86400))
    if interval < 600:
        raise SetupError("free_tick_interval", "Use a free trigger interval of at least ten minutes.")
    tick_cron(interval)
    if answers["database_provider"] == "neon" and interval < 1800:
        raise SetupError("neon_compute_budget", "Use at least 30-minute ticks for the Neon free recipe and measure compute usage.")
    values = dict(FREE_ENV, FREE_TICK_INTERVAL_SECONDS=str(interval))
    for field, name in (
        ("db_cap_bytes", "FREE_DB_CAP_BYTES"), ("object_cap_bytes", "FREE_OBJECT_CAP_BYTES"),
        ("email_daily_cap", "FREE_EMAIL_DAILY_CAP"), ("email_monthly_cap", "FREE_EMAIL_MONTHLY_CAP"),
    ):
        values[name] = positive(caps[field], field)
    values.update(FREE_EMAIL_ACCOUNT_KEY=caps["email_account_key"], FREE_EMAIL_RESET_TIMEZONE=caps["email_reset_timezone"])
    return values
