import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.devices.models import Device, DeviceCommand, PrinterDeviceBinding, PrinterJob
from apps.devices.services_printer_bindings import create_binding, delete_binding, update_binding
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.devices.printer_helpers import printer_case
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def test_bindings_default_to_manual_review_and_reject_cross_tenant_wrong_kind():
    case = printer_case("printer-binding")
    assert case["binding"].auto_apply_terminal is False
    other = printer_case("printer-binding-other")
    with pytest.raises(ValidationError):
        create_binding(case["actor"], case["space"].pk, device_id=other["device"].pk, machine_id=case["machine"].pk)
    Device.objects.filter(pk=case["device"].pk).update(kind="generic")
    delete_binding(case["actor"], case["binding"].pk)
    with pytest.raises(ValidationError):
        create_binding(case["actor"], case["space"].pk, device_id=case["device"].pk, machine_id=case["machine"].pk)


def test_machine_manager_type_assignment_does_not_grant_device_authority():
    from tests.fixed_roles.helpers import assign_builtin_roles
    from tests.return_helpers import make_user
    case = printer_case("printer-scoped-binding")
    actor = make_user("printer-scoped-user", access_status="active", account_kind="staff", staff_makerspace=case['space'])
    assign_builtin_roles(actor, case["space"], "machine_manager", machine_types=[case["machine"].machine_type])
    case["client"].force_authenticate(actor)
    response = case["client"].patch(reverse("devices:admin-printer-binding-detail", args=[case["binding"].pk]),
                                   {"enabled": False}, format="json")
    assert response.status_code == 404
    case["binding"].refresh_from_db()
    assert case["binding"].enabled is True


def test_disabling_or_deleting_binding_cancels_acknowledged_work_and_preserves_history():
    case = printer_case("printer-unbind", leased=True)
    update_binding(case["actor"], case["binding"].pk, {"enabled": False})
    assert DeviceCommand.objects.get(pk=case["job"].command_id).status == "cancelled"
    assert PrinterJob.objects.get(pk=case["job"].pk).state == "cancelled"
    delete_binding(case["actor"], case["binding"].pk)
    assert not PrinterDeviceBinding.objects.filter(pk=case["binding"].pk).exists()
    assert PrinterJob.objects.filter(pk=case["job"].pk).exists()


def test_binding_service_denies_missing_device_authority():
    case = printer_case("printer-no-device-role")
    actor = make_member("printer-machine-manager", case["space"], membership_role="machine_manager", role=User.Role.REQUESTER)
    with pytest.raises(PermissionDenied):
        create_binding(actor, case["space"].pk, device_id=case["device"].pk, machine_id=case["machine"].pk)


def test_explicit_unbind_retires_inert_imported_review_without_workflow_effect():
    case = printer_case("printer-import-review-unbind")
    DeviceCommand.objects.filter(pk=case["job"].command_id).update(status="cancelled")
    PrinterJob.objects.filter(pk=case["job"].pk).update(state="needs_review")
    delete_binding(case["actor"], case["binding"].pk)
    assert PrinterJob.objects.get(pk=case["job"].pk).state == "cancelled"
    case["request"].refresh_from_db()
    assert case["request"].status == "in_progress"
