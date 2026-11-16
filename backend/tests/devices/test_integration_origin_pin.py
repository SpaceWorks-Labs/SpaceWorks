"""#165: the binding detail route names no space, so its target is the binding's own space.

A verified custom staff origin pins every admin route to its space; a person who is staff in
two spaces must not reach the other space's integration binding through it.
"""
import pytest
from django.urls import reverse

from apps.devices.models import MachineTypeIntegration
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import grant_staff_role, make_staff
from tests.devices.sim_agent import enable_integrations
from tests.stage4.helpers import bearer_client
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


def _binding(space):
    enable_integrations(space)
    return MachineTypeIntegration.objects.create(
        makerspace=space, machine_type=machine(space).machine_type,
        kind=MachineTypeIntegration.Kind.PRINTER_AGENT)


def _detail(row):
    return reverse("devices:admin-machine-type-integration-detail", args=[row.pk])


def test_custom_origin_refuses_another_spaces_binding():
    a = Makerspace.objects.create(name="Pin A", slug="pin-a", frontend_domain="pin-a.test",
                                  frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    b = Makerspace.objects.create(name="Pin B", slug="pin-b")
    own, other = _binding(a), _binding(b)
    person = make_staff(a, username="pin-staff")
    grant_staff_role(person, b)
    api = bearer_client(person)
    # Platform origin: staff in both spaces reach both bindings.
    assert api.get(_detail(own)).status_code == 200
    assert api.get(_detail(other)).status_code == 200
    api.credentials(HTTP_AUTHORIZATION=api._credentials["HTTP_AUTHORIZATION"], HTTP_ORIGIN="https://pin-a.test")
    assert api.get(_detail(own)).status_code == 200
    for method in ("get", "patch", "delete"):
        assert getattr(api, method)(_detail(other), {"enabled": True}, format="json").status_code == 403, method
    other.refresh_from_db()
    assert other.enabled is False and MachineTypeIntegration.objects.filter(pk=other.pk).exists()
