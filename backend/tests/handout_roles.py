"""Compatibility helpers for this makerspace's built-in Handover role.

The retained slug/actions parameters cannot customize the fixed catalogue.
"""
from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole

FRONT_DESK_ACTIONS = (
    rbac.Action.VIEW_INVENTORY,
    rbac.Action.ASSIGN_BOX,
    rbac.Action.ISSUE_REQUEST,
    rbac.Action.ISSUE_DIRECT_LOAN,
    rbac.Action.RETURN_REQUEST,
    rbac.Action.UPLOAD_EVIDENCE,
)


def handout_role(makerspace, *, slug="front-desk", actions=FRONT_DESK_ACTIONS):
    """Return the canonical Handover; compatibility arguments do not alter it."""
    return MakerspaceRole.objects.get(makerspace=makerspace, slug="handover")


def grant_handout(user, makerspace, **kwargs):
    """Attach an existing user to this makerspace as front-desk staff."""
    return MakerspaceMembership.staff_tracks.create(
        user=user,
        makerspace=makerspace,
        track=MakerspaceMembership.Track.STAFF,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=handout_role(makerspace, **kwargs),
    )


@transaction.atomic
def make_handout_member(username, makerspace, **kwargs):
    """Create an active user holding only this makerspace's handover role."""
    user = _create_test_user(
        username=username,
        email=f"{username}@e.com",
        role=User.Role.REQUESTER,
        access_status=User.AccessStatus.ACTIVE,
    )
    grant_handout(user, makerspace, **kwargs)
    return user
