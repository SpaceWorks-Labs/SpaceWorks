"""Bounded form (decision 487): the data step runs against the live-schema registry, no schema rewind. The
full rewind-and-replay is in tests/deep_migrations/test_walk_in_email_migration_p7_deep.py."""
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from apps.accounts.models import User

pytestmark = pytest.mark.django_db
migration = import_module("apps.accounts.migrations.0016_clear_walk_in_email_verification")


def test_walk_in_email_verification_is_cleared_by_migration():
    loader = MigrationLoader(connection)
    registry = loader.project_state(loader.graph.leaf_nodes("accounts")).apps
    stamp = timezone.now()
    walk_in = User.objects.create(username="migration-walk-in-email", email="walk-in-migration@example.test",
                                  password="!")
    account = User.objects.create(username="migration-real-account-email", email="account-migration@example.test",
                                  password="!")
    # The historical state this migration repairs: a walk-in carrying a verified-email stamp.
    User.objects.filter(pk=walk_in.pk).update(is_walk_in=True, email_verified_at=stamp)
    User.objects.filter(pk=account.pk).update(is_walk_in=False, email_verified_at=stamp)

    migration.clear_walk_in_email_verification(registry, None)

    assert User.objects.get(pk=walk_in.pk).email_verified_at is None
    assert User.objects.get(pk=account.pk).email_verified_at == stamp
