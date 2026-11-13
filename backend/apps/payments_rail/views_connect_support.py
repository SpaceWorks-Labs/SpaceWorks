"""Callback helpers split out of views_connect.py at the 300-line ceiling.

The two views stay in views_connect.py: the tenant-migration source-gate guards and the
openapi_contract registry pin `views_connect.StripeConnectWebhookView.post` by dotted path,
and tests patch the provider calls on that module.
"""

from django.http import HttpResponseRedirect

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.admin_api.permissions import active_user
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.platform import staff_payment_settings_url
from apps.makerspaces.servability import is_servable


class _PostExchangeRejected(Exception):
    pass


def _redirect(makerspace=None, outcome="failed"):
    response = HttpResponseRedirect(
        staff_payment_settings_url(makerspace, outcome=outcome)
    )
    response["Referrer-Policy"] = "no-referrer"
    return response


def _lock_callback_authority(makerspace_id, actor_id):
    makerspace = Makerspace.objects.select_for_update().get(pk=makerspace_id)
    actor = User.objects.select_for_update().get(pk=actor_id)

    # Space Manager authority lives on the staff-track row (one account per person).
    membership_snapshot = MakerspaceMembership.staff_tracks.filter(
        makerspace_id=makerspace_id,
        user_id=actor_id,
    ).values_list("assigned_role_id", flat=True).first()
    if membership_snapshot:
        MakerspaceRole.objects.select_for_update().get(pk=membership_snapshot)
    membership = (
        MakerspaceMembership.staff_tracks.prefetch_related(additional_roles_prefetch()).select_for_update(of=("self",))
        .select_related("assigned_role")
        .filter(makerspace_id=makerspace_id, user_id=actor_id)
        .first()
    )
    if membership and membership.assigned_role_id != membership_snapshot:
        return makerspace, actor, False

    authorized = bool(
        is_servable(makerspace)
        and active_user(actor)
        and (
            actor.is_superuser or actor.role == User.Role.SUPERADMIN
            or rbac.Action.MANAGE_MAKERSPACE
            in rbac.actions_for_membership(membership)
        )
    )
    return makerspace, actor, authorized
