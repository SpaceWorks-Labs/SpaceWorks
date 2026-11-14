"""Fail-closed settings and CSP for manual Plausible and opt-in Mixpanel."""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def analytics_settings(env, policy):
    script = env("WEB_ANALYTICS_SCRIPT_URL", default="").strip()
    collect = env("WEB_ANALYTICS_COLLECT_URL", default="").strip()
    domain = env("WEB_ANALYTICS_DOMAIN", default="").strip()
    if not any((script, collect, domain)):
        return script, collect, domain
    if not all((script, collect, domain)):
        raise ImproperlyConfigured("All three WEB_ANALYTICS settings are required.")
    origins = []
    for url in (script, collect):
        parts = urlsplit(url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or re.search(r"[\s<>\"'`;\\]", url)):
            raise ImproperlyConfigured("Analytics endpoints must be plain HTTPS URLs.")
        origins.append(f"{parts.scheme}://{parts.netloc}")
    if not re.search(r"[./-]manual[.-]", urlsplit(script).path):
        raise ImproperlyConfigured("Analytics requires a Plausible manual script variant.")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", domain):
        raise ImproperlyConfigured("Analytics domain must be a hostname.")
    directives = policy["DIRECTIVES"]
    directives["script-src"] = [*directives["script-src"], origins[0]]
    directives["connect-src"] = [*directives.get("connect-src", ["'self'"]), origins[1]]
    return script, collect, domain


def mixpanel_settings(env, policy):
    """Operator-only project and exact SDK/collection CSP origins (decision 551)."""
    token = env("WEB_TELEMETRY_MIXPANEL_TOKEN", default="")
    host = env("WEB_TELEMETRY_MIXPANEL_API_HOST", default="") or "https://api.mixpanel.com"
    sdk_host = env("WEB_TELEMETRY_MIXPANEL_SDK_HOST", default="") or "https://cdn.mxpnl.com"
    if not token:
        return "", host, sdk_host
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token):
        raise ImproperlyConfigured("Mixpanel requires a public project token.")
    for origin in (host, sdk_host):
        if not re.fullmatch(r"https://[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*(?::[0-9]{1,5})?", origin):
            raise ImproperlyConfigured("Mixpanel hosts must be bare HTTPS origins.")
    directives = policy["DIRECTIVES"]
    directives["connect-src"] = list(dict.fromkeys([*directives.get("connect-src", ["'self'"]), host]))
    directives["script-src"] = list(dict.fromkeys([*directives["script-src"], sdk_host]))
    return token, host, sdk_host
