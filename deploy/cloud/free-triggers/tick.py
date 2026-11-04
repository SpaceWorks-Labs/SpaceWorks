#!/usr/bin/env python3
"""Optional external free tick caller. Never prints a secret or provider body."""

import os
from pathlib import Path
import stat
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    url = os.environ.get("TICK_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/api/v1/internal/free/tick":
        raise ValueError("invalid target")
    path = Path(os.environ["TICK_SECRET_FILE"])
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("secret link")
    info = path.stat()
    if os.name != "posix" or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > 1024:
        raise ValueError("private secret required")
    secret = path.read_text(encoding="ascii").strip()
    if len(secret) < 32 or any(ord(c) < 33 or ord(c) > 126 for c in secret):
        raise ValueError("secret invalid")
    return url, secret


def main():
    try:
        url, secret = configuration()
        opener = build_opener(NoRedirect)
        for attempt in range(3):
            retry = False
            try:
                request = Request(url, data=b"{}", headers={"X-Cron-Secret": secret, "Content-Type": "application/json"}, method="POST")
                with opener.open(request, timeout=180) as response:
                    # Do not log task/provider failure bodies, even on success.
                    if len(response.read(65537)) > 65536:
                        raise ValueError("response too large")
                    if response.status == 200:
                        print("Free tick accepted; inspect durable task completion separately.")
                        return 0
                    raise ValueError("unexpected success status")
            except HTTPError as exc:
                retry = exc.code in {429, 500, 502, 503, 504}
                exc.close()
                if not retry:
                    raise ValueError("tick rejected") from None
            except (TimeoutError, OSError):
                retry = True
            if retry and attempt < 2:
                time.sleep((10, 30)[attempt])
        raise ValueError("tick unavailable")
    except Exception:
        print("Free tick failed; verify private trigger settings and durable backend status.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
