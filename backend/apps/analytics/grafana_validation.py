"""Decision 263: what a Grafana connection may hold.

A listed dashboard is ``{uid, title, mode, public_token}``. ``mode`` is how the console shows
it: ``public`` frames Grafana's public (shared) dashboard page, whose access token is part of
its URL; ``render`` asks the server to render a PNG through the service-account token, so
Grafana never has to be reachable from the browser. The access token of a public dashboard
is a capability URL, not a credential of this deployment: it is shown to viewers inside the
embed URL anyway, and it never leaves the space because the row is never exported.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext

from .embedding import EmbedUrlInvalid, normalize_site_url

PROVIDERS = ("metabase", "grafana", "both")
MODES = ("public", "render")
UID = re.compile(r"[A-Za-z0-9_-]{1,40}")
PUBLIC_TOKEN = re.compile(r"[0-9a-f]{32}")
MAX_DASHBOARDS = 50


def uses_grafana(provider):
    return provider in ("grafana", "both")


def uses_metabase(provider):
    return provider in ("metabase", "both")


def normalize_grafana_url(value):
    try:
        return normalize_site_url(value)
    except EmbedUrlInvalid:
        raise ValidationError(gettext(
            "The Grafana URL must start with http:// or https:// and carry no credentials, query or fragment."
        )) from None


def validate_grafana_dashboards(value):
    if not isinstance(value, list) or len(value) > MAX_DASHBOARDS:
        raise ValidationError(gettext("Grafana dashboards must be a list of at most 50 entries."))
    seen = set()
    for entry in value:
        if not (isinstance(entry, dict) and set(entry) == {"uid", "title", "mode", "public_token"}):
            raise ValidationError(gettext("Each Grafana dashboard is {uid, title, mode, public_token}."))
        uid, title, mode, token = entry["uid"], entry["title"], entry["mode"], entry["public_token"]
        if not (isinstance(uid, str) and UID.fullmatch(uid)):
            raise ValidationError(gettext("A Grafana dashboard uid is 1 to 40 letters, digits, - or _."))
        if not (isinstance(title, str) and 0 < len(title.strip()) <= 120):
            raise ValidationError(gettext("A dashboard title is 1 to 120 characters."))
        if mode not in MODES:
            raise ValidationError(gettext("A Grafana dashboard is shown as public or render."))
        if not isinstance(token, str) or (token and not PUBLIC_TOKEN.fullmatch(token)):
            raise ValidationError(gettext("A public dashboard access token is 32 lowercase hex characters."))
        if mode == "public" and not token:
            raise ValidationError(gettext("A public dashboard needs its access token."))
        if mode == "render" and token:
            raise ValidationError(gettext("A rendered dashboard has no public access token."))
        if uid in seen:
            raise ValidationError(gettext("A dashboard is listed once."))
        seen.add(uid)
