import pytest
from django.db import DatabaseError, connection, transaction

from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from apps.inventory.purge_equipment_proposals import delete_equipment_proposals
from tests.test_request_workflow import make_space

pytestmark = pytest.mark.django_db(transaction=True)


def test_exact_purge_permit_does_not_delete_another_tenant_snapshot():
    first, second = make_space("equipment-purge-a"), make_space("equipment-purge-b")
    one = EquipmentKitTemplate.objects.create(makerspace=first, name="One")
    two = EquipmentKitTemplate.objects.create(makerspace=second, name="Two")
    v1 = EquipmentKitVersion.objects.create(template=one, version=1, name="One", lines=[])
    v2 = EquipmentKitVersion.objects.create(template=two, version=1, name="Two", lines=[])
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.equipment_purge_model', %s, true), set_config('app.equipment_purge_id', %s, true), set_config('app.equipment_purge_makerspace', %s, true)", [v1._meta.db_table, str(v1.pk), str(second.pk)])
        EquipmentKitVersion.objects.filter(pk=v1.pk).delete()
    with transaction.atomic():
        delete_equipment_proposals(first)
    assert not EquipmentKitVersion.objects.filter(pk=v1.pk).exists()
    assert EquipmentKitVersion.objects.filter(pk=v2.pk).exists()


def test_snapshot_update_remains_forbidden():
    space = make_space("equipment-immutable")
    kit = EquipmentKitTemplate.objects.create(makerspace=space, name="Kit")
    version = EquipmentKitVersion.objects.create(template=kit, version=1, name="Kit", lines=[])
    with pytest.raises(DatabaseError), transaction.atomic():
        EquipmentKitVersion.objects.filter(pk=version.pk).update(name="Changed")
