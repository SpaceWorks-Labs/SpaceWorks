"""#115 parity guard: every Space-Manager surface is reachable by the superadmin, in every space.

No allow-list: a route a Space Manager can open and the superadmin cannot is a gap to fix.
"""

import pytest

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.operations.report_registry import REPORT_DEFINITIONS
from apps.operations.report_subjects import report_action_allowed
from tests.account_split.p1_helpers import staff
from .superadmin_parity_helpers import (PLATFORM_ORIGIN, SHOP_LIST_ROUTES, bearer, census, only_space_kwargs, open_shop,
                                       path_for, shop_census)

pytestmark = pytest.mark.django_db
DENIED = {401, 403}
LEAK = ("parity-leak@example.test", "Qzvleak Parityperson", "+15550004321")


@pytest.fixture
def pii_window(world):
    """A real, audited PII window on every space: reachability is then full Space-Manager parity."""
    from apps.accounts.pii_access import open_grant
    platform = User.objects.get(username="parity-platform")
    for space in Makerspace.objects.filter(slug__in=("parity-a", "parity-b")):
        open_grant(platform, space, "Parity guard: checking every Space-Manager route.")


@pytest.fixture
def world(settings):
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    space = open_shop(Makerspace.objects.create(name="Parity A", slug="parity-a"))
    other = open_shop(Makerspace.objects.create(name="Parity B", slug="parity-b"))
    manager = staff(space, username="parity-sm", role="space_manager")[0]
    platform = User.objects.create_superuser("parity-platform", email="platform@example.test")
    member = User.objects.create_user("parity-member", email=LEAK[0], display_name=LEAK[1], phone=LEAK[2])
    MakerspaceMembership.objects.create(user=member, makerspace=space, role="member",
                                        assigned_role=space.roles.get(slug="member"))
    return space, other, bearer(manager), bearer(platform, origin=PLATFORM_ORIGIN)


def test_census_is_not_empty():
    names = {name for _route, name in census()}
    assert {"admin-email-logs", "report-catalog", "analytics-generic", "report-export",
            "admin-api-settings", "admin-email-templates", "ledger", "delivery-test"} <= names


def test_census_has_the_shop_rows():
    """P38: the shop's staff routes are tenant routes, so the census carries every one of them."""
    names = {name for _route, name in shop_census()}
    assert set(SHOP_LIST_ROUTES) <= names
    assert {"admin-shop-product", "admin-shop-order", "admin-shop-order-receipt", "admin-shop-pos-quote",
            "admin-shop-member-lookup", "admin-shop-cash-session-close"} <= names


def test_superadmin_reaches_every_shop_route(world, pii_window):
    """P38: with the shop on, the Space Manager really opens its lists, and so does the superadmin."""
    space, _other, manager, superadmin = world
    rows = dict((name, route) for route, name in shop_census())
    opened, gaps = [], []
    for name in SHOP_LIST_ROUTES:
        path = path_for(rows[name], space.pk, name)
        sm, sa = manager.get(path).status_code, superadmin.get(path).status_code
        if 200 <= sm < 300:
            opened.append(name)
        if (200 <= sm < 300) != (200 <= sa < 300) or sa in DENIED or sa >= 500:
            gaps.append(f"{name} {path}: space manager {sm}, superadmin {sa}")
    assert opened == list(SHOP_LIST_ROUTES), opened  # the shop world is live, so the comparison is real
    assert not gaps, "\n".join(gaps)


def test_superadmin_reaches_every_space_manager_route(world, pii_window):
    space, _other, manager, superadmin = world
    gaps = []
    for route, name in census():
        path = path_for(route, space.pk, name)
        sm = manager.get(path).status_code
        sa = superadmin.get(path).status_code
        # A route that errors for the Space Manager too is a domain bug, not a parity gap.
        if sm in DENIED or sm >= 500:
            continue
        if sa in DENIED or sa >= 500 or (200 <= sm < 300) != (200 <= sa < 300):
            gaps.append(f"{name} {path}: space manager {sm}, superadmin {sa}")
    assert not gaps, "\n".join(gaps)


def test_superadmin_reaches_every_space_not_only_one(world):
    space, other, _manager, superadmin = world
    for target in (space, other):
        assert superadmin.get(f"/api/v1/admin/makerspace/{target.pk}/reports/catalog").status_code == 200
        assert superadmin.get(f"/api/v1/admin/makerspace/{target.pk}/email-logs").status_code == 200
        assert superadmin.get(f"/api/v1/admin/makerspaces/{target.pk}/shop/orders/").status_code == 200


def test_every_report_definition_is_open_to_the_superadmin(world, pii_window):
    space, _other, manager, superadmin = world
    from apps.accounts.models import User as Model
    actor = Model.objects.get(username="parity-platform")
    tenant = [d for d in REPORT_DEFINITIONS if not d.platform_only]
    assert all(report_action_allowed(actor, d, space.pk) for d in tenant)
    url = f"/api/v1/admin/makerspace/{space.pk}/reports/catalog"
    sm_keys = {row["key"] for row in manager.get(url).json()["results"]}
    sa_keys = {row["key"] for row in superadmin.get(url).json()["results"]}
    assert sm_keys <= sa_keys
    gaps = []
    for definition in tenant:
        path = f"/api/v1/admin/makerspace/{space.pk}/analytics/{definition.key}"
        sm, sa = manager.get(path).status_code, superadmin.get(path).status_code
        if sm not in DENIED and sa in DENIED | {500}:
            gaps.append(f"{definition.key}: space manager {sm}, superadmin {sa}")
    assert not gaps, "\n".join(gaps)


def test_identity_reports_need_a_pii_window(world):
    space, _other, manager, superadmin = world
    path = f"/api/v1/admin/makerspace/{space.pk}/analytics/top-borrowers"
    assert manager.get(path).status_code == 200
    refused = superadmin.get(path)
    assert refused.status_code == 403 and "pii_access_required" in refused.content.decode()


def test_superadmin_never_reads_unwindowed_member_pii(world):
    space, _other, manager, superadmin = world
    members = f"/api/v1/admin/makerspaces/{space.pk}/memberships"
    assert any(value in manager.get(members).content.decode() for value in LEAK)
    leaks = []
    from apps.accounts.surface_policy import _platform_route
    for route, name in census():
        # Platform routes (tenant migration, staff lifecycle) were platform surfaces before
        # #115; their masking is Lane C's adoption list, not this net's.
        if not only_space_kwargs(route, name) or _platform_route(name):
            continue
        response = superadmin.get(path_for(route, space.pk, name))
        body = response.content.decode(errors="ignore")
        leaks += [f"{name} [{response.status_code} masked={response.get('X-PII-Masked')}]: {value} :: {body[:300]}"
                  for value in LEAK if value in body]
    assert not leaks, "\n".join(leaks)
