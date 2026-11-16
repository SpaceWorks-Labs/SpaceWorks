"""Reconciliation preserves quota transferred from profiles to purge journals."""

from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command

from apps.accounts import account_purge_objects as objects
from apps.accounts.models_account_purge import AccountPurgeObject
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import MemberProfile
from tests.accounts import deletion_factories as f
from tests.accounts.test_support_m1d import account, due, m1d_config, purge
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("failure", ["delete", "quota"])
def test_reconciliation_keeps_pending_images_reserved_until_quota_release(failure, monkeypatch):
    user, tenant = due(account()), f.space()
    member = assign_builtin_roles(user, tenant, "member")
    profile = MemberProfile.objects.create(membership=member, avatar_key="member/pending.png")
    InventoryProduct.objects.create(makerspace=tenant, name="Unrelated tool",
                                     image_key="inventory/unrelated.png")
    tenant.storage_bytes_used = 125
    tenant.save(update_fields=["storage_bytes_used"])
    monkeypatch.setattr(objects.limits, "is_self_host", lambda: False)
    monkeypatch.setattr("apps.inventory.public_image_storage.object_size",
                        lambda key: 25 if key == profile.avatar_key else 100)
    monkeypatch.setattr(objects, "_client", Mock())
    delete = Mock(side_effect=OSError("storage unavailable") if failure == "delete" else None)
    real_free = objects.limits.free_storage
    free = Mock(side_effect=OSError("quota unavailable") if failure == "quota" else real_free)
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    monkeypatch.setattr(objects.limits, "free_storage", free)

    assert purge(user)["purged"] == 0
    assert not MemberProfile.objects.filter(pk=profile.pk).exists()
    journal = AccountPurgeObject.objects.get(user=user)
    assert (journal.deleted_at is not None) == (failure == "quota")
    assert journal.quota_released_at is None
    # Includes the reservation even when HEAD would find no remaining bytes.
    call_command("recompute_storage", tenant.slug, stdout=StringIO())
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 125

    delete.side_effect = None
    free.side_effect = real_free
    assert purge(user)["purged"] == 1
    journal.refresh_from_db()
    tenant.refresh_from_db()
    assert journal.quota_released_at and tenant.storage_bytes_used == 100
    calls = free.call_count
    assert purge(user)["purged"] == 0
    assert free.call_count == calls
    call_command("recompute_storage", tenant.slug, stdout=StringIO())
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 100
