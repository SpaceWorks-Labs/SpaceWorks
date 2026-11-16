"""Owner rule (0.12.0, decision 263 addendum): every analytics tool is limited to its space.

The space login that Metabase AND Grafana use is checked over EVERY installed catalogue view:
no other space's rows, no base table at all, and nothing while the module is off. The
platform views and connections stay superadmin-only, and a space's embeds are its own."""

import base64
import hashlib
import hmac
import json

import pytest
from django.apps import apps
from django.db import connection, transaction

from apps.analytics import provisioning
from apps.analytics.catalogue.registry import installed_views
from apps.analytics.models import AnalyticsConnection
from tests.return_helpers import make_product

from .grafana_helpers import G_SPACE_ROUTES, g_platform_url
from .helpers import PLATFORM_ROUTES, SECRET, client_for, manager, platform_url, space, space_url

pytestmark = pytest.mark.django_db(transaction=False)
VIEWS = tuple(installed_views())


def _login(makerspace_id):
    role = provisioning.generate_login_name(makerspace_id)
    provisioning.ensure_login(role, "a-test-password-1234", makerspace_id)
    return role


def _as(role, sql, params=None):
    with transaction.atomic(), connection.cursor() as cursor:
        raw = cursor.cursor
        raw.execute(f'SET LOCAL ROLE "{role}"')
        raw.execute(sql, params)
        rows = raw.fetchall()
        raw.execute("RESET ROLE")
        return rows


@pytest.fixture
def seeded():
    a, b = space("iso-a"), space("iso-b")
    for makerspace in (a, b):
        make_product(makerspace, name=f"item-{makerspace.pk}")
        manager(makerspace, name=f"sm-{makerspace.pk}")
    return a, b


@pytest.mark.parametrize("view", VIEWS, ids=lambda view: view.name)
def test_a_space_login_sees_no_other_space_in_any_view(seeded, view):
    a, _b = seeded
    rows = _as(_login(a.pk), f'SELECT count(*) FROM spaceworks_analytics."{view.name}" '
                             "WHERE makerspace_id IS NOT NULL AND makerspace_id <> %s", [a.pk])
    assert rows == [(0,)]


def test_the_seeded_rows_exist_so_the_filter_is_doing_the_work(seeded):
    a, b = seeded
    everything = _as(_login(None), "SELECT DISTINCT makerspace_id FROM spaceworks_analytics_platform.inventory_products")
    assert {a.pk, b.pk} <= {row[0] for row in everything}
    own = _as(_login(a.pk), "SELECT DISTINCT makerspace_id FROM spaceworks_analytics.inventory_products")
    assert own == [(a.pk,)]


def test_every_space_view_is_pinned_to_the_login_fixed_scope():
    with connection.cursor() as cursor:
        cursor.execute("SELECT viewname, definition FROM pg_views WHERE schemaname = 'spaceworks_analytics'")
        definitions = dict(cursor.fetchall())
    for view in VIEWS:
        assert "spaceworks_rls_fixed_scope" in definitions[view.name], view.name
        assert "enabled_modules" in definitions[view.name] and "lifecycle_state" in definitions[view.name]


def test_a_space_login_cannot_read_any_base_table(seeded):
    a, _b = seeded
    role = _login(a.pk)
    tables = sorted({apps.get_model(label)._meta.db_table for view in VIEWS for label in view.models()})
    assert tables
    for table in tables:
        with pytest.raises(Exception) as error:
            _as(role, f'SELECT 1 FROM public."{table}" LIMIT 1')
        assert "permission denied" in str(error.value), table


def test_module_off_empties_every_view(seeded):
    a, _b = seeded
    role = _login(a.pk)
    a.enabled_modules = sorted(set(a.enabled_modules) - {"analytics"})
    a.save(update_fields=["enabled_modules"])
    for view in VIEWS:
        assert _as(role, f'SELECT count(*) FROM spaceworks_analytics."{view.name}"') == [(0,)], view.name


@pytest.mark.parametrize("method,name,args", PLATFORM_ROUTES)
def test_a_space_manager_never_reaches_the_platform_metabase(method, name, args):
    makerspace = space()
    response = getattr(client_for(manager(makerspace)), method)(platform_url(name, *args), {}, format="json")
    assert response.status_code == 403


@pytest.mark.parametrize("method,name,args", G_SPACE_ROUTES)
def test_a_space_manager_never_reaches_the_platform_grafana(method, name, args):
    makerspace = space()
    response = getattr(client_for(manager(makerspace)), method)(g_platform_url(name, *args), {}, format="json")
    assert response.status_code == 403


def _payload(url):
    token = url.split("/embed/dashboard/")[1].split("#")[0]
    header, body, signature = token.split(".")
    raw = lambda part: base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))  # noqa: E731
    return f"{header}.{body}", json.loads(raw(body)), raw(signature)


def test_a_metabase_embed_is_signed_for_this_space_only():
    a, b = space(), space()
    other_secret = "o" * 64
    for makerspace, secret, board in ((a, SECRET, 1), (b, other_secret, 2)):
        row, _ = AnalyticsConnection.objects.get_or_create(makerspace=makerspace)
        row.metabase_url, row.dashboards = f"https://mb-{makerspace.pk}.example.org", [{"id": board, "title": "D"}]
        row.set_embed_secret(secret)
        row.save()
    client = client_for(manager(a))
    response = client.get(space_url("-embed", a, 1))
    assert response.status_code == 200, response.data
    assert response.data["url"].startswith(f"https://mb-{a.pk}.example.org/")
    signed, payload, signature = _payload(response.data["url"])
    assert payload["resource"] == {"dashboard": 1} and payload["params"] == {}
    assert signature == hmac.new(SECRET.encode(), signed.encode(), hashlib.sha256).digest()
    assert signature != hmac.new(other_secret.encode(), signed.encode(), hashlib.sha256).digest()
    assert client.get(space_url("-embed", a, 2)).data["code"] == "analytics_dashboard_unknown"
    assert client.get(space_url("-embed", b, 2)).status_code == 404
