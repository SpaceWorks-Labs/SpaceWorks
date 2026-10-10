from uuid import uuid4

import pytest
from django.apps import apps
from django.db import connection, transaction

from apps.data_export.guards import validate_all
from apps.data_export.datasets import DATASET_SPECS
from apps.devices.models import LabelPrintCommand, LabelPrintResult
from apps.devices.services_label_results import report_result
from apps.makerspaces.module_purge_collectors_7c import delete_label_commands
from tests.data_export.portable_helpers import archive_files, csv_rows, make_job
from tests.devices.helpers_labels import label_case
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def test_label_model_field_dataset_user_and_reference_catalogs_are_complete():
    validate_all()
    for label in ["devices.LabelPrintCommand", "devices.LabelPrintResult"]:
        assert DATASET_SPECS[label][0].startswith("devices/")
        fields = {field.name for field in apps.get_model(label)._meta.concrete_fields}
        assert not fields & {"object_key", "artifact", "zip_bytes", "pdf_bytes", "url"}


@pytest.mark.parametrize("fidelity", ["REDACTED", "PORTABLE"])
def test_export_contains_label_receipts_and_history_without_stored_bytes(fidelity):
    with enabled_encryption():
        case = label_case(f"label-export-{fidelity.lower()}", acknowledged=True)
        receipt = report_result(case["principal"], case["label"].pk,
                                operation_id=uuid4(), outcome="succeeded", result_code="ok")
        files, _archive, _manifest = archive_files(make_job(case["space"], case["actor"], fidelity=fidelity))
    labels = csv_rows(files, "devices/label_commands.csv")
    results = csv_rows(files, "devices/label_results.csv")
    assert len(labels) == len(results) == 1
    assert labels[0]["batch_id_snapshot"] == str(case["batch"].pk)
    assert labels[0]["result"] == "succeeded"
    assert results[0]["operation_id"] == str(receipt.operation_id)
    assert results[0]["response_command_status"] == "acknowledged"
    assert not any(name.endswith(".svg") or name.startswith("devices/artifacts/") for name in files)
    assert "requested_by_id" in labels[0]


def test_label_purge_deletes_immutable_receipts_before_parents_and_keeps_qr_batch():
    case = label_case("label-purge", acknowledged=True)
    report_result(case["principal"], case["label"].pk,
                  operation_id=uuid4(), outcome="succeeded", result_code="ok")
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        result = delete_label_commands(case["space"])
    assert result["label_result_receipts"] == result["label_print_commands"] == 1
    assert not LabelPrintCommand.objects.exists() and not LabelPrintResult.objects.exists()
    assert case["batch"].items.count() == 2
