"""Decision 263: the parts that reach Grafana or show it: test, embed, render.

Isolation: each call reads ONLY this scope's row, so it uses this space's Grafana URL,
token and organization, and only a dashboard uid listed for this space. The data behind the
dashboard is limited by the space's read-only login (only its own rows, curated views only).
"""

import json

from django.utils.translation import gettext, gettext_noop

from apps.audit.services import record

from . import grafana_client
from .grafana_services import configured_row, listed
from .services import AnalyticsError, _row

_REASONS = {
    "dns_failed": gettext_noop("The Grafana host name could not be resolved."),
    "private_address": gettext_noop("This Grafana address is on a private network, which a space may not use here."),
    "timeout": gettext_noop("Grafana did not answer in time."),
    "connection_failed": gettext_noop("Could not connect to Grafana."),
    "response_too_large": gettext_noop("Grafana sent more than expected."),
}


def _reason(exc):
    return gettext(_REASONS.get(exc.reason, "Could not reach Grafana."))


def _json(body):
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _health(row, allow_private):
    status, _type, body = grafana_client.fetch(row.grafana_url, "/api/health", allow_private=allow_private)
    data = _json(body) if status == 200 else None
    if not isinstance(data, dict) or data.get("database") != "ok":
        return {"name": "health", "ok": False, "detail": gettext("Grafana answered, but not as a healthy Grafana.")}, ""
    version = str(data.get("version") or "")[:40]
    return {"name": "health", "ok": True, "detail": gettext("Grafana is up.")}, version


def _search(row, allow_private):
    if not row.grafana_token:
        return {"name": "search", "ok": False, "detail": gettext("No service-account token is saved.")}, None
    status, _type, body = grafana_client.fetch(
        row.grafana_url, "/api/search", allow_private=allow_private, token=row.get_grafana_token(),
        org_id=row.grafana_org_id, params={"type": "dash-db", "limit": 500})
    if status in (401, 403):
        return {"name": "search", "ok": False, "detail": gettext("Grafana refused the token.")}, None
    data = _json(body) if status == 200 else None
    if not isinstance(data, list):
        return {"name": "search", "ok": False, "detail": gettext("Grafana could not list dashboards.")}, None
    return {"name": "search", "ok": True, "detail": gettext("The token can list dashboards.")}, len(data)


def check_connection(scope, actor):
    row = _row(scope)
    if not row.grafana_url:
        raise AnalyticsError("grafana_not_configured", gettext("Save a Grafana URL first."))
    allow_private = grafana_client.private_hosts_allowed(scope)
    version, found, checks = "", None, []
    try:
        health, version = _health(row, allow_private)
        checks.append(health)
        search, found = _search(row, allow_private)
        checks.append(search)
    except grafana_client.GrafanaUnreachable as exc:
        checks.append({"name": "search" if checks else "health", "ok": False, "detail": _reason(exc)})
    ok = len(checks) == 2 and all(check["ok"] for check in checks)
    record(actor, "analytics.grafana_connection_tested", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "ok": ok})
    return {"ok": ok, "version": version, "dashboards_found": found, "checks": checks}


def embed(scope, actor, uid):
    row = configured_row(scope)
    entry = listed(row, uid)
    if entry["mode"] != "public":
        raise AnalyticsError("grafana_dashboard_unknown", gettext("That dashboard is shown as an image, not embedded."))
    record(actor, "analytics.grafana_dashboard_viewed", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "dashboard": uid, "mode": "public"})
    return {"mode": "public", "url": f"{row.grafana_url}/public-dashboards/{entry['public_token']}"}


def render(scope, actor, uid, *, width, height, theme):
    row = configured_row(scope)
    entry = listed(row, uid)
    if entry["mode"] != "render":
        raise AnalyticsError("grafana_dashboard_unknown", gettext("That dashboard is embedded, not rendered."))
    if not row.grafana_token:
        raise AnalyticsError("grafana_token_missing", gettext("Save a Grafana service-account token first."))
    params = {"orgId": row.grafana_org_id, "width": width, "height": height, "theme": theme, "kiosk": "true"}
    try:
        status, content_type, body = grafana_client.fetch(
            row.grafana_url, f"/render/d/{uid}", allow_private=grafana_client.private_hosts_allowed(scope),
            token=row.get_grafana_token(), org_id=row.grafana_org_id, params=params, accept="image/png",
            limit=grafana_client.IMAGE_LIMIT, read_seconds=grafana_client.RENDER_READ_SECONDS)
    except grafana_client.GrafanaUnreachable as exc:
        raise AnalyticsError("grafana_unreachable", _reason(exc)) from None
    if status != 200 or not content_type.startswith("image/png"):
        raise AnalyticsError("grafana_unreachable", gettext(
            "Grafana did not return an image. Check the token and that the image renderer is installed."))
    record(actor, "analytics.grafana_dashboard_viewed", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "dashboard": uid, "mode": "render"})
    return body
