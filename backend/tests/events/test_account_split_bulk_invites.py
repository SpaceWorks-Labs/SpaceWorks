"""Community invitation delivery must resolve only the matching member identity."""

from unittest.mock import Mock

import pytest

from apps.accounts.models import User
from apps.events.services_bulk_invites import bulk_invites
from tests.account_split.sweep_g2_helpers import staff_user
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("member_exists", [False, True])
def test_bulk_invitation_recipient_never_resolves_same_email_staff_or_platform(monkeypatch, member_exists):
    space = event_space("account-invites")
    space.enabled_modules = sorted({*space.enabled_modules, "email"})
    space.save(update_fields=["enabled_modules"])
    address = "shared-invite@example.test"
    User.objects.create_superuser(username="invite-platform", email=address, password=None)
    staff_user(space, "invite-staff", email=address)
    member = (User.objects.create_user(username="invite-member", email=address)
              if member_exists else None)
    sender = make_staff(space, "invite-sender")
    dispatch = Mock()
    monkeypatch.setattr("apps.events.services_bulk_invites.dispatch_email", dispatch)

    assert bulk_invites(open_event(space), sender, [address]) == 1

    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["recipient_id"] == (member.pk if member else None)
    assert dispatch.call_args.kwargs["to_email"] == address
