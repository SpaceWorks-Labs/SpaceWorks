"""Decision 263 test helpers: Grafana routes, a configured connection and a fake Grafana."""

from django.urls import reverse

from apps.analytics import grafana_client
from apps.analytics.models import AnalyticsConnection, PlatformAnalyticsConnection

TOKEN = "glsa_" + "t" * 40
PUBLIC_TOKEN = "0123456789abcdef0123456789abcdef"
BOARDS = [
    {"uid": "sw-inv", "title": "Inventory", "mode": "public", "public_token": PUBLIC_TOKEN},
    {"uid": "sw-mach", "title": "Machines", "mode": "render", "public_token": ""},
]


def g_space_url(name, makerspace, *args):
    return reverse(f"admin-makerspace-grafana{name}", args=[makerspace.pk, *args])


def g_platform_url(name, *args):
    return reverse(f"admin-platform-grafana{name}", args=list(args))


G_SPACE_ROUTES = (
    ("get", "", ()), ("get", "-connection", ()), ("patch", "-connection", ()), ("post", "-token", ()),
    ("delete", "-token", ()), ("post", "-test", ()), ("get", "-bundle", ()), ("get", "-embed", ("sw-inv",)),
    ("get", "-render", ("sw-mach",)),
)
G_MANAGER_ROUTES = tuple(route for route in G_SPACE_ROUTES if route[1] in
                         ("-connection", "-token", "-test", "-bundle"))


def configure(makerspace=None, *, provider="grafana", url="https://grafana.example.org", token=TOKEN, boards=None):
    if makerspace is None:
        row = PlatformAnalyticsConnection.load()
    else:
        row, _ = AnalyticsConnection.objects.get_or_create(makerspace=makerspace)
    row.provider, row.grafana_url, row.grafana_org_id = provider, url, 3
    row.grafana_dashboards = list(BOARDS if boards is None else boards)
    if token:
        row.set_grafana_token(token)
    row.save()
    return row


class FakeGrafana:
    """Stands in for ``grafana_client.fetch``; records every call (url, path, token, org)."""

    def __init__(self, responses=None, error=None):
        self.calls, self.error = [], error
        self.responses = responses or {
            "/api/health": (200, "application/json", b'{"database":"ok","version":"11.3.0"}'),
            "/api/search": (200, "application/json", b'[{"uid":"a"},{"uid":"b"}]'),
        }

    def __call__(self, base_url, path, *, allow_private, token="", org_id=None, params=None, accept=None,
                 limit=None, read_seconds=None):
        self.calls.append({"base_url": base_url, "path": path, "token": token, "org_id": org_id,
                           "allow_private": allow_private, "params": params})
        if self.error:
            raise grafana_client.GrafanaUnreachable(self.error)
        if path.startswith("/render/"):
            return self.responses.get("render", (200, "image/png", b"\x89PNG fake"))
        return self.responses[path]
