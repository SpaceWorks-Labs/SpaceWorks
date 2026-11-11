"""L25 on L8's seam: a space's analytics login sees only its space's rows, reads views only,
sees member details only when allowed, sees nothing with the module off; the platform login
sees every space and never member details. Postgres, through SET LOCAL ROLE like L8's tests."""

import pytest
from django.db import connection, transaction

from apps.analytics import provisioning
from apps.analytics.models import AnalyticsConnection
from apps.boxes.models import Box  # noqa: F401 - keeps the app import order of L8's tests
from tests.return_helpers import make_product

from .helpers import manager, space

pytestmark = pytest.mark.django_db(transaction=False)


def _login(makerspace_id):
    role = provisioning.generate_login_name(makerspace_id)
    provisioning.ensure_login(role, "a-test-password-1234", makerspace_id)
    return role


def _as(role, sql, params=None):
    """Run one query as the login. A failure rolls the savepoint back, which also undoes the
    SET LOCAL ROLE, so the original error (not an aborted-transaction one) reaches the test."""
    with transaction.atomic(), connection.cursor() as cursor:
        raw = cursor.cursor
        raw.execute(f'SET LOCAL ROLE "{role}"')
        raw.execute(sql, params)
        rows = raw.fetchall()
        raw.execute("RESET ROLE")
        return rows


@pytest.fixture
def two_spaces():
    a, b = space("rls-a"), space("rls-b")
    make_product(a, name="Alpha scope"), make_product(b, name="Beta scope")
    manager(a, name=f"alpha-{a.pk}"), manager(b, name=f"beta-{b.pk}")
    return a, b


def test_a_space_login_sees_only_its_own_rows(two_spaces):
    a, b = two_spaces
    role = _login(a.pk)
    names = {row[0] for row in _as(role, "SELECT name FROM spaceworks_analytics.inventory_products")}
    assert names == {"Alpha scope"}
    spaces = {row[0] for row in _as(role, "SELECT DISTINCT makerspace_id FROM spaceworks_analytics.members")}
    assert spaces == {a.pk}


def test_settings_a_login_sends_cannot_widen_its_scope(two_spaces):
    a, b = two_spaces
    role = _login(a.pk)
    with transaction.atomic(), connection.cursor() as cursor:
        raw = cursor.cursor
        raw.execute(f'SET LOCAL ROLE "{role}"')
        raw.execute("SELECT set_config('app.rls_bound', 'on', true), set_config('app.makerspace_id', %s, true), "
                    "set_config('app.rls_capability', 'backup', true)", [str(b.pk)])
        raw.execute("SELECT name FROM spaceworks_analytics.inventory_products")
        names = {row[0] for row in raw.fetchall()}
        raw.execute("RESET ROLE")
    assert names == {"Alpha scope"}


def test_a_space_login_cannot_read_tables_or_the_platform_schema(two_spaces):
    a, _b = two_spaces
    role = _login(a.pk)
    for sql in ("SELECT 1 FROM public.inventory_inventoryproduct LIMIT 1",
                "SELECT 1 FROM public.analytics_analyticsconnection LIMIT 1",
                "SELECT 1 FROM spaceworks_analytics_platform.inventory_products LIMIT 1"):
        with pytest.raises(Exception) as error:
            _as(role, sql)
        assert "permission denied" in str(error.value)


def test_a_login_is_read_only_and_owns_nothing(two_spaces):
    a, _b = two_spaces
    role = _login(a.pk)
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = %s",
                       [role])
        assert cursor.fetchone() == (False, False, False, False)
        cursor.execute("SELECT count(*) FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = %s)",
                       [role])
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT pg_has_role(%s, 'spaceworks_rls_fixed', 'MEMBER')", [role])
        assert cursor.fetchone()[0] is True


def test_member_details_are_masked_until_the_space_allows_them(two_spaces):
    a, _b = two_spaces
    role = _login(a.pk)
    emails = lambda: {row[0] for row in _as(role, "SELECT email FROM spaceworks_analytics.members")}  # noqa: E731
    assert emails() == {None}
    AnalyticsConnection.objects.update_or_create(makerspace=a, defaults={"show_member_details": True})
    assert any(value and value.endswith("@e.com") for value in emails())


def test_switching_the_module_off_empties_the_views(two_spaces):
    a, _b = two_spaces
    role = _login(a.pk)
    a.enabled_modules = sorted(set(a.enabled_modules) - {"analytics"})
    a.save(update_fields=["enabled_modules"])
    assert _as(role, "SELECT count(*) FROM spaceworks_analytics.inventory_products") == [(0,)]


def test_built_in_machine_types_are_listed_to_a_space_login(two_spaces):
    from apps.machines.models import MachineType
    a, _b = two_spaces
    MachineType.objects.get_or_create(slug="l25-builtin", makerspace=None, defaults={"name": "Built-in"})
    role = _login(a.pk)
    query = "SELECT slug FROM spaceworks_analytics.machine_types"
    # Decision 263 isolation pass: unowned rows follow the login's own space switches too.
    a.enabled_modules = sorted(set(a.enabled_modules) - {"machines"})
    a.save(update_fields=["enabled_modules"])
    assert "l25-builtin" not in {row[0] for row in _as(role, query)}
    a.enabled_modules = sorted({*a.enabled_modules, "machines"})
    a.save(update_fields=["enabled_modules"])
    assert "l25-builtin" in {row[0] for row in _as(role, query)}


def test_the_platform_login_sees_every_space_and_never_member_details(two_spaces):
    a, b = two_spaces
    AnalyticsConnection.objects.update_or_create(makerspace=a, defaults={"show_member_details": True})
    role = _login(None)
    names = {row[0] for row in _as(role, "SELECT name FROM spaceworks_analytics_platform.inventory_products")}
    assert {"Alpha scope", "Beta scope"} <= names
    emails = {row[0] for row in _as(role, "SELECT email FROM spaceworks_analytics_platform.members")}
    assert emails == {None}
    with pytest.raises(Exception):
        _as(role, "SELECT 1 FROM spaceworks_analytics.inventory_products LIMIT 1")


def test_views_catalog_lists_the_version():
    role = _login(space().pk)
    rows = _as(role, "SELECT DISTINCT views_version FROM spaceworks_analytics.views_catalog")
    from apps.analytics.catalogue.registry import VIEWS_VERSION
    assert rows == [(VIEWS_VERSION,)]
