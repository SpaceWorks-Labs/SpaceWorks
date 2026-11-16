"""Decision 263: the Grafana provisioning bundle of one space (or of the platform).

It holds a PostgreSQL data source that uses THIS scope's read-only login (host, database
and user from the existing login; never another space's, never a table) and the starter
dashboards of the areas that are on. It never carries a secret: the password field is a
placeholder the operator replaces with the password shown once at create or rotate (the
console can fill it in the browser right after that, the server never re-sends it).
"""

import io
import json
import zipfile
from ipaddress import ip_address

from django.utils.translation import gettext

from apps.makerspaces.platform import module_enabled

from . import provisioning
from .catalogue.registry import VIEWS_VERSION
from .grafana_dashboards import AREAS, MODULE, dashboard

FORMAT = "spaceworks-grafana-bundle"
VERSION = 1
PASSWORD_PLACEHOLDER = "PASTE_PASSWORD_HERE"
DATASOURCE_TYPE = "grafana-postgresql-datasource"
DASHBOARD_DIR = "/var/lib/grafana/dashboards/spaceworks"


def _tag(scope):
    return "p" if scope.platform else f"s{scope.makerspace.pk}"


def areas(scope):
    if scope.platform:
        return list(AREAS)
    return [area for area in AREAS if MODULE[area] is None or module_enabled(scope.makerspace, MODULE[area])]


def _sslmode(host):
    try:
        address = ip_address(host)
        return "disable" if (address.is_loopback or address.is_private) else "require"
    except ValueError:
        return "disable" if (host == "localhost" or "." not in host) else "require"


def _datasource(scope, row, details):
    label = "platform" if scope.platform else f"space {scope.makerspace.pk}"
    return {
        "apiVersion": 1,
        "datasources": [{
            "name": f"SpaceWorks analytics ({label})", "uid": f"sw-{_tag(scope)}-pg", "type": DATASOURCE_TYPE,
            "access": "proxy", "url": f"{details['host']}:{details['port']}", "user": row.login_role,
            "jsonData": {"database": details["database"], "sslmode": _sslmode(details["host"]),
                         "postgresVersion": 1600, "timescaledb": False, "maxOpenConns": 5},
            "secureJsonData": {"password": PASSWORD_PLACEHOLDER},
            "editable": True,
        }],
    }


def build(scope, row):
    details = provisioning.connection_details(platform=scope.platform)
    source = _datasource(scope, row, details)
    reference = {"type": DATASOURCE_TYPE, "uid": source["datasources"][0]["uid"]}
    label = "platform" if scope.platform else "space"
    chosen = areas(scope)
    boards = [{"area": area, "uid": f"sw-{_tag(scope)}-{area}",
               "title": f"SpaceWorks {label}: {area}",
               "dashboard": dashboard(area, uid=f"sw-{_tag(scope)}-{area}", datasource=reference,
                                      schema=details["schema"], label=label)}
              for area in chosen]
    return {
        "format": FORMAT, "version": VERSION, "scope": scope.label,
        "makerspace_id": None if scope.platform else scope.makerspace.pk,
        "views_version": VIEWS_VERSION, "ready": bool(row.login_role), "areas": chosen,
        "datasource": source, "dashboards": boards,
        "instructions": [
            gettext("Create the read-only database login in SpaceWorks first; the user name above is that login."),
            gettext("Replace %(placeholder)s with the password SpaceWorks showed when the login was created "
                    "or rotated. SpaceWorks never stores it in a form it can show again.")
            % {"placeholder": PASSWORD_PLACEHOLDER},
            gettext("Use sslmode require (or verify-full) when Grafana reaches the database over a network."),
            gettext("Import each dashboard (Dashboards > New > Import) or provision them from the zip bundle."),
        ],
    }


def to_zip(bundle):
    """The same bundle as Grafana provisioning files (JSON is valid YAML)."""
    buffer = io.BytesIO()
    provider = {"apiVersion": 1, "providers": [{
        "name": "spaceworks", "folder": "SpaceWorks", "type": "file", "disableDeletion": False,
        "options": {"path": DASHBOARD_DIR}}]}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("provisioning/datasources/spaceworks.yaml", json.dumps(bundle["datasource"], indent=2))
        archive.writestr("provisioning/dashboards/spaceworks.yaml", json.dumps(provider, indent=2))
        for entry in bundle["dashboards"]:
            archive.writestr(f"dashboards/spaceworks/{entry['area']}.json", json.dumps(entry["dashboard"], indent=2))
        archive.writestr("README.txt", "\n".join(bundle["instructions"]) + "\n")
    return buffer.getvalue()
