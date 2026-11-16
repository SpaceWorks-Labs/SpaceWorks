"""Undefined imports found by the branch-wide review sweep fail at the boundary."""
import pytest
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import ValidationError

from apps.hardware_requests.self_checkout_views import _require_module
from apps.machines.models import MachineType, MakerspaceMachineTypePricing
from apps.makerspaces.models import Makerspace


def test_public_tool_module_guard_reports_disabled_module():
    space = Makerspace(name="Disabled", slug="disabled", enabled_modules=[])
    from apps.makerspaces.guards import SurfaceOff  # #183B: an off module answers 404, not 400
    with pytest.raises(SurfaceOff, match="qr_system is turned off"):
        _require_module(space, "qr_system")
    space.enabled_modules = ["qr_system"]
    _require_module(space, "qr_system")


@pytest.mark.parametrize("type_space", [None, 1, 2])
def test_machine_pricing_rejects_foreign_tenant_types(type_space):
    machine_type = MachineType(id=1, makerspace_id=type_space, name="Type", slug="type")
    pricing = MakerspaceMachineTypePricing(makerspace_id=1, machine_type=machine_type)
    if type_space == 2:
        with pytest.raises(ModelValidationError, match="belong to this makerspace"):
            pricing.clean()
    else:
        pricing.clean()
