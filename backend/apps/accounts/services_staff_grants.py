"""Native staff grants: a step-up on a person, fixed to one makerspace (Q12).

A staff device grant is only as good as the staff role it was issued for. Losing that
role revokes every staff grant the person holds in that makerspace, so a phone cannot
keep staff authority the console has already taken away. Three paths enforce it:

- ``revoke_staff_grants`` is the seam role-changing services call (U-B's staff-roles API);
- a membership signal revokes after any staff-track row change commits;
- every device request and refresh re-checks the role (``staff_role_state``), so even a
  bulk ``update()`` that fires no signal cannot leave a usable staff grant behind.

A makerspace that is only temporarily unservable refuses the grant without revoking it.
"""

import logging

from django.db import transaction

from apps.accounts import audit_events

logger = logging.getLogger(__name__)
ACTIVE, LOST, UNSERVABLE = "active", "lost", "unservable"


def staff_role_state(user, makerspace_id):
    """``active`` (usable), ``unservable`` (row kept, space unavailable) or ``lost``."""
    from apps.accounts.membership_context import valid_staff_membership_q
    from apps.accounts.staff_identity import has_staff_role
    from apps.makerspaces.models import MakerspaceMembership

    if has_staff_role(user, makerspace_id):
        return ACTIVE
    held = MakerspaceMembership.staff_tracks.filter(
        valid_staff_membership_q(), user_id=user.pk, makerspace_id=makerspace_id, status="active",
    ).exists()
    return UNSERVABLE if held else LOST


@transaction.atomic
def revoke_staff_grants(user, makerspace_id=None, *, reason, actor=None):
    """Revoke the person's active staff grants (in one makerspace, or everywhere)."""
    from apps.accounts.models_devices import DeviceGrant
    from apps.accounts.services_tokens import revoke_device_grant

    grants = DeviceGrant.objects.filter(user_id=user.pk, authority=DeviceGrant.Authority.STAFF,
                                        status=DeviceGrant.Status.ACTIVE, revoked_at__isnull=True)
    if makerspace_id is not None:
        grants = grants.filter(staff_makerspace_id=makerspace_id)
    revoked = 0
    for grant in grants.order_by("pk"):
        revoke_device_grant(grant)
        revoked += 1
        _audit_revoked(actor, user, grant, reason)
    return revoked


def _audit_revoked(actor, user, grant, reason):
    from apps.makerspaces.models import Makerspace

    audit_events.record_auth_event(
        actor, "auth.staff_grant_revoked", target=user,
        makerspace=Makerspace.objects.filter(pk=grant.staff_makerspace_id).first(),
        meta={"grant_hash": audit_events.fingerprint(grant.pk), "reason": reason},
    )


def audit_issued(user, grant):
    from apps.makerspaces.models import Makerspace

    audit_events.record_auth_event(
        user, "auth.staff_grant_issued", target=user,
        makerspace=Makerspace.objects.filter(pk=grant.staff_makerspace_id).first(),
        meta={"grant_hash": audit_events.fingerprint(grant.pk), "login_method": grant.login_method},
    )


def revoke_if_role_lost(user, makerspace_id, *, reason="staff_role_revoked"):
    """Revoke in its own transaction when the role is gone; returns the role state."""
    state = staff_role_state(user, makerspace_id)
    if state == LOST:
        revoke_staff_grants(user, makerspace_id, reason=reason)
    return state


def _membership_changed(sender, instance, **kwargs):
    if getattr(instance, "track", None) != "staff" or kwargs.get("raw"):
        return
    from apps.accounts.models import User

    def _after_commit():
        user = User.objects.filter(pk=instance.user_id).first()
        if user is None:
            return
        try:
            revoke_if_role_lost(user, instance.makerspace_id)
        except Exception:  # never fail the role change itself; requests re-check anyway
            logger.exception("Staff grant revocation after a role change failed",
                             extra={"user_id": instance.user_id, "makerspace_id": instance.makerspace_id})

    transaction.on_commit(_after_commit)


def connect_signals():
    from django.db.models.signals import post_delete, post_save
    from apps.makerspaces.models import MakerspaceMembership

    post_save.connect(_membership_changed, sender=MakerspaceMembership,
                      dispatch_uid="accounts.staff_grants.membership_saved")
    post_delete.connect(_membership_changed, sender=MakerspaceMembership,
                        dispatch_uid="accounts.staff_grants.membership_deleted")
