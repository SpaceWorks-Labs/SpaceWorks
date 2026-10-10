import pytest
from rest_framework.exceptions import ValidationError

from apps.operations.services_qr_assets import add_qr_to_batch, mark_batch_printed
from tests.devices.helpers_labels import label_case

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", ["printed", "archived"])
def test_non_draft_batch_cannot_add_or_relabel_even_with_a_stale_instance(status):
    case = label_case(f"qr-freeze-{status}")
    batch = case["batch"]
    item = batch.items.first()
    from apps.operations.models import QrPrintBatch
    QrPrintBatch.objects.filter(pk=batch.pk).update(status=status)
    with pytest.raises(ValidationError):
        add_qr_to_batch(batch, item.qr_code, label_text="Changed")
    item.refresh_from_db()
    assert item.label_text != "Changed"
    assert batch.items.count() == 2


def test_manual_mark_printed_uses_the_same_freeze_boundary_as_device_send():
    case = label_case("qr-freeze-manual")
    mark_batch_printed(case["actor"], case["batch"])
    item = case["batch"].items.first()
    response = case["client"].post(f"/api/v1/admin/qr-print-batches/{case['batch'].pk}/items",
        {"qr_code_id": item.qr_code_id, "label_text": "Replacement"}, format="json")
    assert response.status_code == 400
    item.refresh_from_db()
    assert item.label_text != "Replacement"
