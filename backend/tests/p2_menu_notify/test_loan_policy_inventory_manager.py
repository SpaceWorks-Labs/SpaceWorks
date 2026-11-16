"""menu-notify carry-over: the loan policy belongs to the Inventory Manager too."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def path(space):
    return f"/api/v1/admin/makerspace/{space.pk}/return-policy"


def test_inventory_manager_reads_and_updates_the_loan_policy_with_audit():
    space = make_space("policy-inventory")
    manager = make_member("policy-inventory-manager", space,
                          membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    client = client_for(manager)
    assert client.get(path(space)).status_code == 200
    response = client.patch(path(space), {"default_loan_days": 5}, format="json")
    assert response.status_code == 200, response.data
    space.refresh_from_db()
    assert space.default_loan_days == 5
    assert MakerspaceLoanPolicy.objects.get(makerspace=space).default_loan_days == 5
    assert AuditLog.objects.filter(actor=manager, action="makerspace.return_policy_updated", makerspace=space).exists()


def test_inventory_manager_stays_scoped_to_their_own_space():
    space = make_space("policy-inventory-home")
    other = make_space("policy-inventory-away")
    manager = make_member("policy-inventory-scoped", space,
                          membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    assert client_for(manager).patch(path(other), {"default_loan_days": 2}, format="json").status_code == 404


def test_roles_without_lending_authority_are_refused():
    space = make_space("policy-machine-only")
    machine = make_member("policy-machine-manager", space,
                          membership_role=MakerspaceMembership.Role.MACHINE_MANAGER, role=User.Role.REQUESTER)
    client = client_for(machine)
    assert client.get(path(space)).status_code == 404
    assert client.patch(path(space), {"default_loan_days": 2}, format="json").status_code == 404
    space.refresh_from_db()
    assert space.default_loan_days == 7


def test_service_refuses_an_actor_without_either_action():
    from rest_framework.exceptions import PermissionDenied

    from apps.makerspaces.loan_policy_settings import update_loan_policy

    space = make_space("policy-service-refusal")
    machine = make_member("policy-service-machine", space,
                          membership_role=MakerspaceMembership.Role.MACHINE_MANAGER, role=User.Role.REQUESTER)
    with pytest.raises(PermissionDenied):
        update_loan_policy(machine, space, {"default_loan_days": 3})
