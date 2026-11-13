"""L17 superadmin capability purge (#128 C-8): per parent, switched off first, re-auth, preview."""
import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.capability_purge import preview, purge_capability, purgeable_capabilities
from apps.procurement.models import ToBuyItem
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def superadmin(name="purge-root"):
    return make_user(name, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
                     is_staff=True, is_superuser=True)


@pytest.fixture
def space():
    space = make_space("cap-purge")
    ToBuyItem.objects.create(makerspace=space, kind="printing", name="PLA")
    ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Probe")
    return space


def off(space, key):
    space.refresh_from_db()
    space.enabled_features = [k for k in space.enabled_features if k != key]
    space.save(update_fields=["enabled_features"])


def test_purging_machines_tobuy_never_deletes_inventory_rows(space):
    root = superadmin()
    assert preview(space, "machines.tobuy") == {"to_buy_items": 1, "receipts": 0}
    with pytest.raises(ValidationError):  # still switched on
        purge_capability(space, "machines.tobuy", root)
    off(space, "machines.tobuy")
    counts = purge_capability(space, "machines.tobuy", root)
    assert counts == {"to_buy_items": 1}
    assert list(ToBuyItem.objects.filter(makerspace=space).values_list("kind", flat=True)) == ["hardware"]
    row = AuditLog.objects.get(action="makerspace.capability_purged", makerspace=space)
    assert row.meta["capability"] == "machines.tobuy" and row.actor == root
    assert AuditLog.objects.filter(action="makerspace.capability_purge_started", makerspace=space).exists()


def test_only_a_superadmin_purges(space):
    off(space, "inventory.tobuy")
    manager = make_user("purge-sm")
    with pytest.raises(ValidationError):
        purge_capability(space, "inventory.tobuy", manager)
    with pytest.raises(ValidationError):
        purge_capability(space, "machines.issue_reporting", superadmin("purge-root-2"))  # L16: owns no rows
    assert ToBuyItem.objects.filter(makerspace=space).count() == 2


def test_control_page_previews_and_needs_recent_reauth_and_typed_confirmation(space):
    root = superadmin("purge-root-3")
    url = reverse("admin:makerspaces_makerspace_capability_purge", args=[space.pk])
    stale = Client()
    stale.force_login(root)
    assert stale.post(url, {"key": "inventory.tobuy", "confirm": "inventory.tobuy"}).status_code == 302
    assert ToBuyItem.objects.filter(makerspace=space).count() == 2
    client = Client()
    force_recent_control_login(client, root)
    page = client.get(url)
    assert page.status_code == 200 and b"inventory.tobuy" in page.content
    off(space, "inventory.tobuy")
    client.post(url, {"key": "inventory.tobuy", "confirm": "wrong"})
    assert ToBuyItem.objects.filter(makerspace=space).count() == 2
    client.post(url, {"key": "inventory.tobuy", "confirm": "inventory.tobuy"})
    assert list(ToBuyItem.objects.filter(makerspace=space).values_list("kind", flat=True)) == ["printing"]
    plans = {row["key"]: row for row in purgeable_capabilities(space)}
    assert plans["inventory.tobuy"]["switched_on"] is False and plans["machines.tobuy"]["counts"]["to_buy_items"] == 1
