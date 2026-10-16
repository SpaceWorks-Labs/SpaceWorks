"""The one table of in-app link destinations native apps open (mobile plan, phase 1e item 3).

Shared by push `link` values (phase 1b) and the deep-link association files (phase 1e), so a
link a notification carries is always one the installed app claims. Anything outside it --
staff `/m/<slug>/admin/*`, `/control/`, public pages not listed -- opens in the browser.
Pure data and string matching: no I/O, no settings.
"""

import re

_SEGMENT = r"[^/?#]+"

# (name, shared-host pattern, custom-domain pattern). A verified custom domain names the
# makerspace through its host, so its paths carry no `/m/<slug>` prefix. `None` means the
# destination has no form on that host type.
DESTINATIONS = (
    ("member_home", "/m/{slug}/member", "/member"),
    ("member_tab", "/m/{slug}/member/{tab}", "/member/{tab}"),
    ("member_account", "/m/{slug}/member/account", "/member/account"),
    ("event_ticket", "/m/{slug}/member/events/{registration}/ticket",
     "/member/events/{registration}/ticket"),
    ("event", "/m/{slug}/events/{token}", "/events/{token}"),
    ("booking", "/m/{slug}/bookings/{token}", "/bookings/{token}"),
    ("item", "/m/{slug}/items/{item}", "/items/{item}"),
)

# Prefixes the association files list as explicit exclusions.
EXCLUDED_PREFIXES = ("/m/{slug}/admin", "/control", "/admin", "/api", "/docs", "/redoc", "/schema")


def _regex(pattern):
    body = re.sub(r"\{[a-z_]+\}", _SEGMENT, pattern)
    return re.compile(rf"^{body}/?$")


_COMPILED = tuple(
    _regex(pattern)
    for _name, shared, custom in DESTINATIONS
    for pattern in (shared, custom)
    if pattern
)


def is_supported_link(path):
    """True only for a local path (no scheme, host, query or fragment) the app claims."""
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return False
    if any(char in path for char in "?#\\") or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    return any(regex.match(path) for regex in _COMPILED)


def association_patterns():
    """`(shared, custom)` glob patterns for the association files (`*` per segment)."""
    def glob(pattern):
        return re.sub(r"\{[a-z_]+\}", "*", pattern) if pattern else None

    return [(glob(shared), glob(custom)) for _name, shared, custom in DESTINATIONS]
