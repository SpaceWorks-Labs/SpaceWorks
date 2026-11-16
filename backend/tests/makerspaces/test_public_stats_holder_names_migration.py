"""Bounded form (decision 487): the data step runs against the live-schema registry, no schema rewind. The
full rewind-and-replay is in tests/deep_migrations/test_public_stats_holder_names_migration_deep.py."""
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db
migration = import_module("apps.makerspaces.migrations.0060_makerspace_public_stats_show_holder_names")


def test_existing_makerspaces_enable_holder_names_but_new_ones_default_off():
    loader = MigrationLoader(connection)
    registry = loader.project_state(loader.graph.leaf_nodes("makerspaces")).apps
    existing = Makerspace.objects.create(
        name="Existing private stats space", slug="existing-private-stats-space", public_stats_enabled=False)
    Makerspace.objects.filter(pk=existing.pk).update(public_stats_show_holder_names=False)

    migration.enable_holder_names(registry, None)

    assert Makerspace.objects.get(pk=existing.pk).public_stats_show_holder_names is True
    created_after_upgrade = Makerspace.objects.create(name="New holder-private space", slug="new-holder-private-space")
    assert created_after_upgrade.public_stats_show_holder_names is False

    migration.disable_holder_names(registry, None)
    assert Makerspace.objects.get(pk=existing.pk).public_stats_show_holder_names is False
