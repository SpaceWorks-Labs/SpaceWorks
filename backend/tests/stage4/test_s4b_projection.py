"""Exact-tenant retirement guards survive a deployment with several staff tenants."""
from pathlib import Path
from datetime import datetime, timezone as datetime_timezone

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.models import User, UserMFA
from apps.backup import archive_builder
from apps.backup.outer_manifest import verify_outer_manifest
from apps.backup.projection_databases import restore_dump, temporary_database
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.account_split.p1_helpers import staff
from tests.backup.conftest import installed_producer_capability  # noqa: F401
from tests.backup.test_compound_archive_e3 import allow_projection_databases  # noqa: F401
from tests.backup import test_compound_archive_e3 as e3

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("managed", [False, True])
def test_three_purges_in_one_outer_transaction_finish_each_tenants_guards(settings, monkeypatch, managed):
    settings.MANAGED_POSTGRES = managed
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_storage_keys", lambda keys: None)
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_public_image_keys", lambda keys: None)
    owner = User.objects.create_superuser("s4b-purge-owner")
    spaces, accounts = [], []
    for index in range(3):
        space = Makerspace.objects.create(name=f"Purge {index}", slug=f"s4b-purge-{index}", archived_at=timezone.now())
        account, _ = staff(space, f"s4b-purge-staff-{index}")
        spaces.append(space)
        accounts.append(account)
    with transaction.atomic():
        for space in spaces:
            purge(space, owner)
    assert not Makerspace.objects.filter(pk__in=[space.pk for space in spaces]).exists()
    for account in accounts:
        account.refresh_from_db()
        assert account.retired_at is not None and account.staff_makerspace_id is None


def test_exact_tenant_guard_is_not_widened_to_another_staff_membership():
    first = Makerspace.objects.create(name="Guard A", slug="s4b-guard-a")
    second = Makerspace.objects.create(name="Guard B", slug="s4b-guard-b")
    _account, membership = staff(second, "s4b-guard-b-staff")
    membership_id = membership.pk
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)", [str(first.pk)])
        membership.delete()
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert MakerspaceMembership.objects.filter(pk=membership_id).exists()
