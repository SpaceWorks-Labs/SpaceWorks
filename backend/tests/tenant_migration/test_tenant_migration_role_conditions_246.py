"""Decision 246 (lane T4): tenant-migration routes are superadmin-only (role matrix, RM row).

Every built-in role and anonymous callers are refused on the platform pairing/import routes and the
per-space export, quiesce, disclosure and archive routes. Nothing is written. The self-host move
REQUEST route is deliberately staff-visible and is not part of this matrix.
"""
import uuid

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.r2_superadmin_local.helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin"
REFUSED = (401, 403, 404)
ZERO = uuid.UUID(int=0)


def routes(lab):
    migration = f"{ADMIN}/makerspace/{lab.pk}/tenant-migration"
    imports = f"{ADMIN}/platform/tenant-migrations/imports"
    return [
        ("get", f"{ADMIN}/platform/tenant-migrations/deployment-identity", None),
        ("get", f"{ADMIN}/platform/tenant-migrations/pairings", None),
        ("post", f"{ADMIN}/platform/tenant-migrations/pairings", {}),
        ("get", imports, None),
        ("post", imports, {}),
        ("post", f"{imports}/uploads", {}),
        ("get", f"{imports}/{ZERO}", None),
        ("post", f"{imports}/{ZERO}/run", {}),
        ("post", f"{imports}/{ZERO}/identity-decisions", {}),
        ("get", f"{imports}/{ZERO}/verification", None),
        ("get", f"{migration}/disclosure-closure", None),
        ("get", f"{migration}/disclosure-approvals", None),
        ("post", f"{migration}/disclosure-approvals", {}),
        ("get", f"{migration}/exports", None),
        ("post", f"{migration}/exports", {}),
        ("get", f"{migration}/exports/{ZERO}", None),
        ("post", f"{migration}/exports/{ZERO}/quiesce", {}),
        ("post", f"{migration}/pairings/{ZERO}/archive-source", {}),
        ("post", f"{migration}/pairings/{ZERO}/recover", {}),
    ]


def call(client, verb, url, body):
    return getattr(client, verb)(url, body, format="json") if body is not None else getattr(client, verb)(url)


@pytest.mark.parametrize("slug", [role.slug for role in ROLE_CATALOG])
def test_no_built_in_role_reaches_a_tenant_migration_route(slug):
    lab = space(f"tm-{slug}".replace("_", "-"))
    client = api(staff_account(lab, f"tm-actor-{slug}", slug))
    before = AuditLog.objects.count()
    for verb, url, body in routes(lab):
        assert call(client, verb, url, body).status_code in REFUSED, (slug, verb, url)
    assert AuditLog.objects.count() == before


def test_anonymous_is_refused_on_every_tenant_migration_route():
    lab = space("tm-anon")
    for verb, url, body in routes(lab):
        assert call(api(), verb, url, body).status_code in (401, 403), (verb, url)


def test_the_superadmin_is_not_refused_on_the_identity_and_list_routes():
    lab = space("tm-root")
    root = api(superadmin())
    for url in (f"{ADMIN}/platform/tenant-migrations/deployment-identity",
                f"{ADMIN}/platform/tenant-migrations/imports",
                f"{ADMIN}/makerspace/{lab.pk}/tenant-migration/exports"):
        assert root.get(url).status_code not in (401, 403), url
