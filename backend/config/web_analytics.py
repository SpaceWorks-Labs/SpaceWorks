"""Fail-closed settings for the one supported, manual Plausible protocol."""
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
