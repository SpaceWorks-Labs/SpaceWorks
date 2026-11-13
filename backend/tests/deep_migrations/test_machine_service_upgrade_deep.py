"""Deep-rewind migration test (runs in the CI migration-rewind slices: it uses MigrationExecutor).

Moved from tests/test_machine_service_models.py, which now carries the bounded form (decision 474).
"""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_machine_service_migrations_upgrade_from_real_heads_deep():
    from_target = [("machines", "0007_machine_usage_time_index"), ("makerspaces", "0039_seed_and_backfill_roles")]
    target = [("machines", "0008_machine_service_requests"), ("makerspaces", "0040_machine_service_module")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(from_target)
        old_apps = executor.loader.project_state(from_target).apps
        OldMakerspace = old_apps.get_model("makerspaces", "Makerspace")
        OldMachineType = old_apps.get_model("machines", "MachineType")
        OldMachine = old_apps.get_model("machines", "Machine")
        makerspace = OldMakerspace.objects.create(
            name="Migration service", slug="migration-service", enabled_modules=["machines"]
        )
        machine_type = OldMachineType.objects.create(
            makerspace_id=makerspace.id, slug="migration-service", name="Migration service"
        )
        OldMachine.objects.create(makerspace_id=makerspace.id, machine_type_id=machine_type.id, name="Migrated")

        executor = MigrationExecutor(connection)
        executor.migrate(target)
        new_apps = executor.loader.project_state(target).apps
        NewMakerspace = new_apps.get_model("makerspaces", "Makerspace")
        assert new_apps.get_model("machines", "MachineServiceRequest").objects.count() == 0
        assert new_apps.get_model("machines", "ServiceBucket").objects.count() == 0
        assert "machine_service" in NewMakerspace.objects.get(pk=makerspace.id).enabled_modules
    finally:
        restore = MigrationExecutor(connection)
        restore.migrate(restore.loader.graph.leaf_nodes())
