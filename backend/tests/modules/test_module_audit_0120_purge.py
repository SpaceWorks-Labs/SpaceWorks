"""Module audit 0.12.0: switching off keeps data; the separate superadmin purge removes ALL of it.

The devices purge left `MachineTypeIntegration` (the per-type integration binding) behind, so a
reinstall brought half-configured bindings back. It is deleted with the rest of the module now.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.devices.models import MachineTypeIntegration
from apps.makerspaces.module_purge import purge_module
from tests.devices.sim_agent import enable_integrations
from tests.module_helpers import disable_module
from tests.return_helpers import make_space
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


def _binding(space):
    enable_integrations(space)
    return MachineTypeIntegration.objects.create(
        makerspace=space, machine_type=machine(space).machine_type, kind=MachineTypeIntegration.Kind.PRINTER_AGENT)


def test_uninstalling_devices_keeps_the_integration_bindings():
    space = make_space("audit-purge-keep")
    binding = _binding(space)

    disable_module(space, "devices")

    assert MachineTypeIntegration.objects.filter(pk=binding.pk).exists()


def test_purging_devices_removes_the_integration_bindings_of_that_space_only():
    space, other = make_space("audit-purge-devices"), make_space("audit-purge-other")
    binding, kept = _binding(space), _binding(other)
    disable_module(space, "devices")
    root = get_user_model().objects.create_superuser("audit-purge-root", "audit-purge-root@example.test", "x")

    counts = purge_module(space, "devices", root)

    assert counts["machine_type_integrations"] == 1
    assert not MachineTypeIntegration.objects.filter(pk=binding.pk).exists()
    assert MachineTypeIntegration.objects.filter(pk=kept.pk).exists()
