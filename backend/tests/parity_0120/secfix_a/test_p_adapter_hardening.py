"""SECFIX-A: security review hardening 6 (a `pending-` vendor job id) and 7 (label print with no binding)."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.devices.models import AdapterBinding, AdapterCommand, PrinterJob
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.parity_0120.adapter_api.test_job_dispatch import dispatched

pytestmark = pytest.mark.django_db(transaction=True)


def test_an_ack_with_the_reserved_placeholder_prefix_is_a_typed_400_not_a_500():
    case = dispatched("secfix-ack-pending")
    job = case["sim"].post("jobs/lease").data["job"]
    refused = case["sim"].post(f"jobs/{job['job_id']}/ack",
                               {"lease_token": job["lease_token"], "external_job_id": "pending-123"})
    assert refused.status_code == 400 and refused.data["code"] == "external_job_id_reserved"
    assert PrinterJob.objects.get(pk=job["job_id"]).external_job_id.startswith("pending-")  # still unbound
    acked = case["sim"].post(f"jobs/{job['job_id']}/ack",
                             {"lease_token": job["lease_token"], "external_job_id": "vendor-7"})
    assert acked.status_code == 200  # the lease was not spent by the refusal
    assert PrinterJob.objects.get(pk=job["job_id"]).external_job_id == "vendor-7"


def test_a_label_for_an_adapter_with_no_label_binding_is_refused_not_a_crash():
    from apps.devices.services_adapter_label import notify_adapter
    case = adapter_case("secfix-label-none")
    AdapterBinding.objects.filter(device=case["device"]).update(enabled=False)
    label = type("Label", (), {"pk": 1, "batch_id_snapshot": 1, "item_count_snapshot": 1})()
    with pytest.raises(ValidationError):
        notify_adapter(case["manager"], label, case["device"])
    assert not AdapterCommand.objects.filter(capability="label.print").exists()
