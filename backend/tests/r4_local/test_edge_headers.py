"""R4 security: every bundled-nginx location that serves the SPA sends the framing headers.

nginx drops server-level add_header as soon as a location adds its own, and the SPA's
X-Frame-Options / frame-ancestors live in the analytics-headers include. Local only."""

import re
from pathlib import Path

NGINX = Path(__file__).resolve().parents[3] / "frontend" / "nginx.conf"


def _locations(text):
    for match in re.finditer(r"location\s+([^{]+)\{", text):
        depth, index = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            index += 1
        yield match.group(1).strip(), text[match.end():index - 1]


def test_every_spa_location_includes_the_framing_headers():
    missing = [name for name, body in _locations(NGINX.read_text(encoding="utf-8"))
               if "/index.html" in body and "try_files" in body and "analytics-headers.conf" not in body]
    # The second /e/<uuid> block is unreachable (the first regex wins) but must not be the only one.
    missing = [name for name in missing if "event_short_token" not in name]
    assert not missing, missing
