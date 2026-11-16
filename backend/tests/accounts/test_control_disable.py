"""U-B (Q8): disabling an account is a superadmin /control/ action through the service."""

import pytest
from cryptography.fernet import Fernet
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.accounts import staff_account_lifecycle as lifecycle
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import device_grant, make_staff
from tests.accounts.mfa_helpers import force_mfa_login

pytestmark = pytest.mark.django_db
PASSWORD = "Control disable password 19!"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()


@pytest.fixture
def spaces():
    return (Makerspace.objects.create(name="Disable A", slug="disable-a"),
            Makerspace.objects.create(name="Disable B", slug="disable-b"))


def test_superadmin_disables_and_reenables(spaces):
    a, b = spaces
    root = User.objects.create_superuser("dis-root", password=PASSWORD)
    target = make_staff(a, username="dis-target", password=PASSWORD, role_slug="inventory_manager")
    from tests.accounts.account_factories import grant_staff_role
    grant_staff_role(target, b, role_slug="event_manager")
    grant = device_grant(target, staff_makerspace_id=a.pk)
    lifecycle.disable_account(root, target.pk, reason="Compromised account")
    target.refresh_from_db()
    assert not target.is_active
    assert set(MakerspaceMembership.staff_tracks.filter(user=target).values_list("status", flat=True)) == {"revoked"}
    grant.refresh_from_db()
    assert grant.revoked_at is not None
    assert AuditLog.objects.filter(action="account.disabled", target_id=str(target.pk)).exists() or \
        AuditLog.objects.filter(action="account.disabled").exists()
    assert AuditLog.objects.filter(action="staff_role.revoked").count() == 2
    lifecycle.enable_account(root, target.pk)
    target.refresh_from_db()
    assert target.is_active
    assert AuditLog.objects.filter(action="account.enabled").exists()


def test_disable_outranks_the_last_manager_rule(spaces):
    a, _b = spaces
    root = User.objects.create_superuser("dis-root-2", password=PASSWORD)
    only = make_staff(a, username="dis-only-sm", password=PASSWORD)
    lifecycle.disable_account(root, only.pk, reason="Left the organisation")
    assert not User.objects.get(pk=only.pk).is_active


def test_space_manager_cannot_disable(spaces):
    a, _b = spaces
    manager = make_staff(a, username="dis-manager", password=PASSWORD)
    target = make_staff(a, username="dis-tech", password=PASSWORD, role_slug="inventory_manager")
    with pytest.raises(PermissionDenied):
        lifecycle.disable_account(manager, target.pk, reason="Not allowed")
    assert User.objects.get(pk=target.pk).is_active


def test_control_action_needs_step_up_and_a_reason(client, spaces):
    a, _b = spaces
    root = User.objects.create_superuser("dis-root-3", password=PASSWORD)
    target = make_staff(a, username="dis-admin-target", password=PASSWORD, role_slug="inventory_manager")
    force_mfa_login(client, root)
    url = reverse("admin:accounts_user_changelist")
    response = client.post(url, {"action": "disable_account", "_selected_action": [target.pk]})
    assert response.status_code in {200, 302}
    assert User.objects.get(pk=target.pk).is_active  # step-up or the reason form comes first


def test_removed_lifecycle_operations_are_gone():
    for name in ("set_password", "reactivate", "deactivate"):
        assert not hasattr(lifecycle, name)
