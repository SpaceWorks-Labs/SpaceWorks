import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.machines.models import Machine, MachineConsumablePool, MachineServiceRequest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("debug", [True, False])
def test_seed_demo_creates_three_spaces_staff_and_inventory(settings, debug):
    settings.DEBUG = debug
    call_command("seed_demo", password="same-pass-123", allow_production_demo=not debug)

    spaces = {space.slug: space for space in Makerspace.objects.all()}
    assert set(spaces) == {"alpha-lab", "beta-workshop", "gamma-fab"}
    assert spaces["beta-workshop"].location == "North Wing - Woodshop"

    for username in ("superadmin", "alpha_manager", "beta_manager", "gamma_manager"):
        user = User.objects.get(username=username)
        assert user.check_password("same-pass-123")
        assert user.account_kind == ("platform" if username == "superadmin" else "staff")
        if user.account_kind == "staff":
            assert user.makerspace_memberships.count() == 1
            assert user.staff_makerspace_id == user.makerspace_memberships.get().makerspace_id

    assert MakerspaceMembership.objects.filter(
        makerspace=spaces["beta-workshop"],
        role=MakerspaceMembership.Role.SPACE_MANAGER,
    ).exists()
    assert InventoryProduct.objects.count() == 15
    assert InventoryAsset.objects.count() == 9
    assert Machine.objects.filter(machine_type__slug="3d_printer").count() == 3
    assert MachineConsumablePool.objects.filter(material="PLA", remaining_grams="1000.00").count() == 3
    assert not MachineServiceRequest.objects.exclude(requester__account_kind="member").exists()
    assert MachineServiceRequest.objects.filter(title="Demo 3D print request", status="pending").count() == 3


def test_seed_demo_refuses_production_before_writing_any_rows(settings):
    settings.DEBUG = False
    users, spaces = User.objects.count(), Makerspace.objects.count()
    with pytest.raises(CommandError, match="--allow-production-demo"):
        call_command("seed_demo")
    assert User.objects.count() == users
    assert Makerspace.objects.count() == spaces
    assert not InventoryProduct.objects.exists()



def test_production_setup_instance_creates_only_operator_identity_and_space(settings):
    settings.DEBUG = False
    call_command('setup_instance', username='operator', email='owner@example.org',
                 password='operator-private-password', makerspace_name='Operator Lab', profile='minimal')
    assert list(User.objects.values_list('username', flat=True)) == ['operator']
    assert list(Makerspace.objects.values_list('name', flat=True)) == ['Operator Lab']
    assert not InventoryProduct.objects.exists()
    assert not InventoryAsset.objects.exists()
    assert not Machine.objects.exists()
