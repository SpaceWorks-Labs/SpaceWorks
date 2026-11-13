"""`revoke_authentication` reports the push devices it switched off, not zero.

Revoking a device grant already invalidates that grant's push destinations, so a count taken
AFTER the grants go read zero for devices this very revocation had silenced. The count is now
taken before, and the audit/summary of a credential revocation names the real number.
"""
import pytest
from django.utils import timezone

from apps.accounts.credential_revocation_helpers import revoke_authentication
from apps.integrations.models import PushDevice
from tests.accounts.account_factories import device_grant
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def _push(user, space, grant, index):
    device = PushDevice(user=user, makerspace=space, device_grant=grant, provider="fcm",
                        environment="development", token_fingerprint=str(index) * 64)
    device.set_token(f"push-secret-{index}")
    device.save()
    return device


def test_the_count_includes_devices_switched_off_by_revoking_their_grant():
    space = make_space("rev-push-count")
    user = make_member("rev-push-count-user", space)
    grant = device_grant(user)
    _push(user, space, grant, 1)
    _push(user, space, grant, 2)

    counts = revoke_authentication(user, now=timezone.now())

    assert counts["push_devices"] == 2
    assert counts["device_grants"] == 1
    assert not PushDevice.objects.filter(user=user, active=True).exists()


def test_already_inactive_devices_are_not_counted():
    space = make_space("rev-push-inactive")
    user = make_member("rev-push-inactive-user", space)
    grant = device_grant(user)
    _push(user, space, grant, 3)
    PushDevice.objects.filter(user=user).update(active=False)

    assert revoke_authentication(user, now=timezone.now())["push_devices"] == 0
