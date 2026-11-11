"""Decision 263: the provisioning bundle uses only this scope's login and curated views, follows
the area modules, and never carries a secret (password, token, embed secret, public token)."""

import io
import json
import re
import zipfile

import pytest

from apps.analytics.catalogue.registry import installed_views
from apps.analytics.db_names import PLATFORM_SCHEMA, SPACE_SCHEMA
from apps.analytics.grafana_bundle import PASSWORD_PLACEHOLDER
from apps.audit.models import AuditLog

from .grafana_helpers import PUBLIC_TOKEN, TOKEN, configure, g_platform_url, g_space_url
from .helpers import SECRET, client_for, manager, space, space_url, superadmin

pytestmark = pytest.mark.django_db
QUALIFIED = re.compile(r"\b(spaceworks_analytics(?:_platform|_admin)?)\.([a-z_]+)")


def _with_login(makerspace, client):
    created = client.post(space_url("-login", makerspace))
    assert created.status_code == 201, created.data
    return created.data


def _sql(bundle):
    return [target["rawSql"] for board in bundle["dashboards"] for panel in board["dashboard"]["panels"]
            for target in panel["targets"]]


def test_the_space_bundle_names_its_own_login_and_no_secret():
    makerspace = space()
    row = configure(makerspace)
    row.set_embed_secret(SECRET)
    row.save()
    client = client_for(manager(makerspace))
    credentials = _with_login(makerspace, client)
    response = client.get(g_space_url("-bundle", makerspace))
    assert response.status_code == 200, response.data
    assert response["Cache-Control"] == "no-store" and "attachment" in response["Content-Disposition"]
    bundle = response.data
    source = bundle["datasource"]["datasources"][0]
    assert source["user"] == credentials["role"] and f"_s{makerspace.pk}_" in source["user"]
    assert source["secureJsonData"] == {"password": PASSWORD_PLACEHOLDER}
    assert bundle["scope"] == "space" and bundle["makerspace_id"] == makerspace.pk and bundle["ready"] is True
    text = json.dumps(bundle, default=str)
    for secret in (credentials["password"], TOKEN, SECRET, PUBLIC_TOKEN):
        assert secret not in text
    assert len(bundle["datasource"]["datasources"]) == 1
    entry = AuditLog.objects.get(makerspace=makerspace, action="analytics.grafana_bundle_downloaded")
    assert entry.meta["areas"] == bundle["areas"]


def test_every_query_reads_only_curated_views_of_the_space_schema():
    makerspace = space()
    makerspace.enabled_modules = sorted({*makerspace.enabled_modules, "machines", "events", "bookings", "membership"})
    makerspace.save(update_fields=["enabled_modules"])
    bundle = client_for(manager(makerspace)).get(g_space_url("-bundle", makerspace)).data
    allowed = {view.name for view in installed_views()} - {"prize_payouts"}
    assert set(bundle["areas"]) == {"inventory", "machines", "events", "bookings", "money", "membership"}
    for sql in _sql(bundle):
        named = QUALIFIED.findall(sql)
        assert named, sql
        assert {schema for schema, _view in named} == {SPACE_SCHEMA}
        assert {view for _schema, view in named} <= allowed
        assert "public." not in sql and "payout" not in sql
    datasource_uid = bundle["datasource"]["datasources"][0]["uid"]
    for board in bundle["dashboards"]:
        for panel in board["dashboard"]["panels"]:
            assert panel["datasource"]["uid"] == datasource_uid


def test_an_area_whose_module_is_off_is_left_out():
    makerspace = space()
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules) - {"machines", "events", "bookings",
                                                                           "membership"})
    makerspace.save(update_fields=["enabled_modules"])
    bundle = client_for(manager(makerspace)).get(g_space_url("-bundle", makerspace)).data
    assert bundle["areas"] == ["inventory", "money"]
    assert bundle["ready"] is False and bundle["datasource"]["datasources"][0]["user"] == ""


def test_the_platform_bundle_uses_the_platform_schema_and_every_area():
    bundle = client_for(superadmin()).get(g_platform_url("-bundle")).data
    assert bundle["scope"] == "platform" and bundle["makerspace_id"] is None
    assert len(bundle["areas"]) == 6
    for sql in _sql(bundle):
        assert {schema for schema, _view in QUALIFIED.findall(sql)} == {PLATFORM_SCHEMA}


def test_the_zip_holds_grafana_provisioning_files_and_no_secret():
    makerspace = space()
    configure(makerspace)
    client = client_for(manager(makerspace))
    credentials = _with_login(makerspace, client)
    response = client.get(g_space_url("-bundle", makerspace), {"archive": "zip"})
    assert response.status_code == 200 and response["Content-Type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"provisioning/datasources/spaceworks.yaml", "provisioning/dashboards/spaceworks.yaml",
            "dashboards/spaceworks/inventory.json", "README.txt"} <= names
    blob = b"".join(archive.read(name) for name in names).decode()
    assert credentials["password"] not in blob and TOKEN not in blob
    assert json.loads(archive.read("provisioning/datasources/spaceworks.yaml"))["datasources"][0]["user"] == \
        credentials["role"]
