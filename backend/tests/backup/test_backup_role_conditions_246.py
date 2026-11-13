"""Decision 246 (lane T4): backup and restore routes are superadmin-only (role matrix, RM row).

Every built-in role (even in its own space) and anonymous callers are refused on the platform and
per-space backup, restore, off-site destination and download-url routes; nothing is created and no
audit row is written. The superadmin reaches the read routes. Runs under the isolated runner like the
rest of `tests/backup`.
"""
import uuid

import pytest

from apps.audit.models import AuditLog
from apps.backup.models import BackupArchive, RestoreOperation
from apps.makerspaces.role_catalog import ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.r2_superadmin_local.helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin"
REFUSED = (401, 403, 404)
ZERO = uuid.UUID(int=0)


def routes(lab):
    return [
        ("get", f"{ADMIN}/platform/backup-settings", None),
        ("put", f"{ADMIN}/platform/backup-settings", {}),
        ("get", f"{ADMIN}/platform/backups", None),
        ("post", f"{ADMIN}/platform/backups", {}),
        ("get", f"{ADMIN}/platform/backup-destinations", None),
        ("post", f"{ADMIN}/platform/backup-destinations", {}),
        ("post", f"{ADMIN}/platform/backup-destinations/push", {}),
        ("post", f"{ADMIN}/platform/backups/{ZERO}/rehydrate", {}),
        ("get", f"{ADMIN}/platform/restores", None),
        ("post", f"{ADMIN}/platform/restores", {}),
        ("get", f"{ADMIN}/platform/restores/{ZERO}", None),
        ("post", f"{ADMIN}/platform/restores/{ZERO}/decision", {}),
        ("get", f"{ADMIN}/makerspace/{lab.pk}/backups", None),
        ("post", f"{ADMIN}/makerspace/{lab.pk}/backups", {}),
        ("get", f"{ADMIN}/backups/{ZERO}/download-url", None),
    ]


def _audited():
    # `rls.capability_used` is the tenant-RLS boundary's sampled infrastructure row (first use per
    # process per route); it records that a capability was bound, not that a role did anything.
    return AuditLog.objects.exclude(action="rls.capability_used").count()


def call(client, verb, url, body):
    return getattr(client, verb)(url, body, format="json") if body is not None else getattr(client, verb)(url)


@pytest.mark.parametrize("slug", [role.slug for role in ROLE_CATALOG])
def test_no_built_in_role_reaches_a_backup_or_restore_route(slug):
    lab = space(f"bk-{slug}".replace("_", "-"))
    client = api(staff_account(lab, f"bk-actor-{slug}", slug))
    before = _audited()
    for verb, url, body in routes(lab):
        assert call(client, verb, url, body).status_code in REFUSED, (slug, verb, url)
    assert not BackupArchive.objects.exists() and not RestoreOperation.objects.exists()
    assert _audited() == before


def test_anonymous_is_refused_on_every_backup_route():
    lab = space("bk-anon")
    for verb, url, body in routes(lab):
        assert call(api(), verb, url, body).status_code in (401, 403), (verb, url)


def test_the_superadmin_reaches_the_read_routes():
    lab = space("bk-root")
    root = api(superadmin())
    for url in (f"{ADMIN}/platform/backup-settings", f"{ADMIN}/platform/backups", f"{ADMIN}/platform/restores",
                f"{ADMIN}/platform/backup-destinations", f"{ADMIN}/makerspace/{lab.pk}/backups"):
        assert root.get(url).status_code == 200, url


def test_another_spaces_manager_is_refused_even_for_their_own_spaces_backups():
    mine, other = space("bk-own"), space("bk-other")
    manager = api(staff_account(mine, "bk-own-mgr", "space_manager"))
    assert manager.get(f"{ADMIN}/makerspace/{mine.pk}/backups").status_code in REFUSED
    assert manager.get(f"{ADMIN}/makerspace/{other.pk}/backups").status_code in REFUSED
