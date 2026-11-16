from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    make_role_account as _make_role_account,
)
from rest_framework.test import APIClient
from tests.p3_fixbe_helpers import staff_presence

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MakerspaceWaiver
from apps.makerspaces.waiver_services import accept_waiver


def active_member_client(
    makerspace,
    username,
    *,
    display_name=None,
    email=None,
    phone="1234567890",
):
    """Create an eligible member and authenticate an API client as that member."""
    user = _make_role_account(
        makerspace,
        role_slug=(MakerspaceRole.objects.get(
            makerspace=makerspace,
            slug="member",
        )).slug,
        username=username,
        password="password",
        display_name=display_name or username,
        email=email or f"{username}@example.test",
        phone=phone,
        access_status=User.AccessStatus.ACTIVE,
    )
    membership = _configured_membership(user=user, makerspace=makerspace)
    if MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True).exists():
        accept_waiver(membership)
    staff_presence(user, makerspace, 60)
    client = APIClient()
    client.force_authenticate(user)
    return user, client
