"""Bounded form (decision 487) of the machine-type backfill test: the migration's data step runs against
the live-schema registry, with no schema rewind. The full rewind-and-replay is in
tests/deep_migrations/test_procurement_machine_type_migration_deep.py (CI migration slices)."""
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.machines.models import Machine, MachineConsumablePool, MachineType
from apps.procurement.models import ToBuyItem
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
migration = import_module("apps.procurement.migrations.0007_tobuyitem_machine_type")


def test_machine_type_backfill_uses_only_ordered_durable_provenance_and_reverses():
    loader = MigrationLoader(connection)
    registry = loader.project_state(loader.graph.leaf_nodes("procurement")).apps
    space = make_space("migration-lab")
    result_type = MachineType.objects.create(makerspace=space, slug="result-type", name="Result type")
    source_type = MachineType.objects.create(makerspace=space, slug="source-type", name="Source type")
    pool_type = MachineType.objects.create(makerspace=space, slug="pool-type", name="Pool type")
    result_machine = Machine.objects.create(makerspace=space, machine_type=result_type, name="Result machine")
    source_machine = Machine.objects.create(makerspace=space, machine_type=source_type, name="Source machine")
    pool_machine = Machine.objects.create(makerspace=space, machine_type=pool_type, name="Pool machine")

    def pool(name, machine=None):
        return MachineConsumablePool.objects.create(
            makerspace=space, machine=machine, material=name, initial_grams="100.00", remaining_grams="100.00")

    source_pool, resulting_pool, shared_pool = pool("source", source_machine), pool("resulting", pool_machine), pool("shared")
    rows = {
        "result": ToBuyItem.objects.create(makerspace=space, kind="printing", name="result",
                                           resulting_machine=result_machine),
        "source": ToBuyItem.objects.create(makerspace=space, kind="printing", name="source", source_pool=source_pool),
        "pool": ToBuyItem.objects.create(makerspace=space, kind="printing", name="pool",
                                         resulting_pool=resulting_pool),
        "priority": ToBuyItem.objects.create(makerspace=space, kind="printing", name="priority",
                                             resulting_machine=result_machine, source_pool=source_pool,
                                             resulting_pool=resulting_pool),
        "shared": ToBuyItem.objects.create(makerspace=space, kind="printing",
                                           name="Filament restock: guessed name must not count",
                                           source_pool=shared_pool),
        "none": ToBuyItem.objects.create(makerspace=space, kind="printing",
                                         name="3D printer-looking name must not count"),
    }
    ToBuyItem.objects.filter(pk__in=[row.pk for row in rows.values()]).update(machine_type=None)

    migration.backfill_machine_type(registry, None)

    stamped = {key: ToBuyItem.objects.get(pk=row.pk).machine_type_id for key, row in rows.items()}
    assert stamped == {"result": result_type.pk, "source": source_type.pk, "pool": pool_type.pk,
                       "priority": result_type.pk, "shared": None, "none": None}

    # The explicit NULL-clearing reverse the executor would run before dropping the column.
    migration.clear_machine_type(registry, None)
    assert set(ToBuyItem.objects.filter(pk__in=[row.pk for row in rows.values()])
               .values_list("machine_type_id", flat=True)) == {None}
