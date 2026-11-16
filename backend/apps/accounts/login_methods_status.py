"""Read-only status lines for the ``/control/`` *Login methods* page (S-C)."""

from django.conf import settings
from django.utils.html import format_html, format_html_join


def protection_summary():
    """Turnstile, the breached-password check and automatic IP blocking, as configured."""
    if settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY:
        hosts = ", ".join(settings.TURNSTILE_HOSTNAMES) or "each verified origin's own host"
        turnstile = (f"On for {hosts}: asked after {settings.TURNSTILE_AFTER_FAILURES} failed sign-ins and "
                     f"instead of an automatic block; if Cloudflare is unreachable the sign-in is "
                     f"{'let through' if settings.TURNSTILE_FAIL_MODE == 'open' else 'refused'}.")
    else:
        turnstile = "Off: set TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY to use it."
    breach = (f"On: Have I Been Pwned range check, {settings.PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS} s limit, "
              "a password is accepted when the service cannot be reached."
              if settings.PASSWORD_BREACH_CHECK_ENABLED else "Off (PASSWORD_BREACH_CHECK_ENABLED).")
    blocking = (f"On: {settings.LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS} different accounts failing from one address "
                f"within {settings.LOGIN_IP_BLOCK_WINDOW_SECONDS // 60} min blocks it for "
                f"{settings.LOGIN_IP_BLOCK_SECONDS // 60} min."
                if settings.LOGIN_IP_BLOCK_ENABLED else "Off (LOGIN_IP_BLOCK_ENABLED).")
    rows = (("CAPTCHA (Cloudflare Turnstile)", turnstile), ("Breached-password check", breach),
            ("Automatic IP blocking", blocking))
    return format_html("<dl>{}</dl>", format_html_join("", "<dt><strong>{}</strong></dt><dd>{}</dd>", rows))
