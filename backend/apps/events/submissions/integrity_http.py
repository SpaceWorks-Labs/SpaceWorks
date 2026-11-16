"""The bounded outbound adapter `integrity.check_github` expects (G10).

Pinned host, HTTPS only, no redirects, a short timeout and a response byte cap. An
optional `GITHUB_API_TOKEN` raises the rate limit; without it GitHub's anonymous limit
applies. Any failure raises; the caller turns that into "no flag, try later", never a
verdict about the project.
"""

import json
import urllib.request
from urllib.parse import urlsplit

from django.conf import settings


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHubHttp:
    def get_json(self, url, *, allowed_host, timeout_seconds, max_bytes, allow_redirects=False):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != allowed_host or parts.port not in (None, 443):
            raise ValueError("Refused outbound host")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "SpaceWorks"}
        token = (getattr(settings, "GITHUB_API_TOKEN", "") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        handlers = [] if allow_redirects else [_NoRedirect()]
        opener = urllib.request.build_opener(*handlers)
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout_seconds) as response:
            if response.status != 200:
                raise ValueError("Unexpected status")
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("Response too large")
        return json.loads(raw)
