import pytest
from django.db import DatabaseError, connection, transaction

from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from tests.return_helpers import make_space


@pytest.mark.django_db(transaction=True)
def test_version_requires_exact_model_row_and_tenant_purge_scope():
    maker = make_space("equipment-immutable")
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="First")
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="First", lines=[])
    with pytest.raises(DatabaseError), transaction.atomic():
        EquipmentKitVersion.objects.filter(pk=version.pk).update(name="Changed")
    with pytest.raises(DatabaseError), transaction.atomic():
        EquipmentKitVersion.objects.filter(pk=version.pk).delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.equipment_purge_model', %s, true)", [version._meta.db_table])
            cursor.execute("SELECT set_config('app.equipment_purge_id', %s, true)", [str(version.pk)])
            cursor.execute("SELECT set_config('app.equipment_purge_makerspace', %s, true)", [str(maker.pk + 1)])
        EquipmentKitVersion.objects.filter(pk=version.pk).delete()
    assert EquipmentKitVersion.objects.filter(pk=version.pk).exists()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.equipment_purge_model', %s, true)", [version._meta.db_table])
            cursor.execute("SELECT set_config('app.equipment_purge_id', %s, true)", [str(version.pk)])
            cursor.execute("SELECT set_config('app.equipment_purge_makerspace', %s, true)", [str(maker.pk)])
        EquipmentKitVersion.objects.filter(pk=version.pk).delete()
    assert not EquipmentKitVersion.objects.filter(pk=version.pk).exists()
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.equipment_purge_id', true)")
        assert cursor.fetchone()[0] in (None, "")
