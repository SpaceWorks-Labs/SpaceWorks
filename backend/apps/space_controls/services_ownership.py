"""Transfer ownership: the superadmin names a new Space Manager (#185 item 3).

Built entirely from the staff-role services, so their rules still hold: only the
superadmin grants or removes the Space Manager role (#110, Q14), the last active manager
is protected, the staff quota and tenant gate apply, and each step is audited by its own
service. The new manager is made first, then the previous manager is kept as staff
(with the roles chosen), revoked, or left as a co-manager. Everything commits together.

A person with a row in the space (community or staff) is promoted at once. Anyone else
gets a Space Manager invitation by email and the previous manager is left untouched
until the invitee accepts; the superadmin then runs the transfer again.
"""

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.staff_identity import person_q
from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import is_servable

from .errors import SpaceControlConflict
from .write_policy import control_context

SPACE_MANAGER = "space_manager"
OUTCOMES = ("keep_staff", "revoke", "keep_manager")


def _clean(email, outcome, previous_roles):
    email = str(email or "").strip().lower()
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError({"email": exc.messages}) from exc
    if outcome not in OUTCOMES:
        raise ValidationError({"previous_outcome": f"Choose one of: {', '.join(OUTCOMES)}."})
    roles = list(previous_roles or [])
    if outcome == "keep_staff" and (not roles or SPACE_MANAGER in roles):
        raise ValidationError({"previous_roles": "Choose the staff roles the previous manager keeps."})
    return email, roles


def _previous(space, membership_id):
    if membership_id is None:
        return None
    row = MakerspaceMembership.staff_tracks.filter(
        pk=membership_id, makerspace=space, status="active", assigned_role__slug=SPACE_MANAGER,
    ).first()
    if row is None:
        raise ValidationError({"previous_membership_id": "Choose an active Space Manager of this space."})
    return row


def _promote(actor, space, person):
    from apps.accounts import staff_account_lifecycle as lifecycle
    from apps.accounts import staff_account_services as services
    from apps.accounts.staff_account_policy import role_keys

    row = MakerspaceMembership.staff_tracks.filter(makerspace=space, user=person).first()
    if row is not None:
        if row.status != "active":
            row = lifecycle.restore(actor, space.pk, row.pk)
        if role_keys(row) != [SPACE_MANAGER]:
            services.change(actor, space.pk, row.pk, roles=[SPACE_MANAGER])
        return True
    if MakerspaceMembership.objects.filter(makerspace=space, user=person, status="active").exists():
        services.grant(actor, space.pk, user_id=person.pk, roles=[SPACE_MANAGER])
        return True
    return False


def transfer_ownership(actor, makerspace_id, *, email, previous_membership_id=None,
                       previous_outcome="keep_staff", previous_roles=()):
    """Returns ``(status, invitation_delivery_status)``; status is transferred | invited."""
    from apps.accounts import staff_account_lifecycle as lifecycle
    from apps.accounts import staff_account_services as services
    from apps.accounts.services_staff_invitations import issue, onboarding_available

    require_platform_superadmin(actor)
    email, roles = _clean(email, previous_outcome, previous_roles)
    invitation = None
    with transaction.atomic(), control_context():
        space = Makerspace.objects.get(pk=makerspace_id)
        if not is_servable(space):
            raise SpaceControlConflict("space_not_active", "Ownership can be transferred only in an active space.")
        previous = _previous(space, previous_membership_id)
        person = User.objects.filter(person_q(), email__iexact=email).first()
        if person is not None and previous is not None and person.pk == previous.user_id:
            raise ValidationError({"email": "This person is already the Space Manager you are replacing."})
        if person is None or not _promote(actor, space, person):
            if not onboarding_available(space):
                raise SpaceControlConflict(
                    "invitation_unavailable",
                    "This person has no account in the space and email invitations are off here. Turn on "
                    "the Email module, or ask them to join the space first.")
            invitation = issue(actor, space.pk, email=email, roles=[SPACE_MANAGER])
            audit.record(actor, "space_control.ownership_invited", makerspace=space, target=space,
                         meta={"invitation_id": invitation[0].pk})
        else:
            if previous is not None and previous_outcome == "keep_staff":
                services.change(actor, space.pk, previous.pk, roles=roles)
            elif previous is not None and previous_outcome == "revoke":
                lifecycle.revoke(actor, space.pk, previous.pk, reason="Ownership transferred to a new Space Manager")
            audit.record(actor, "space_control.ownership_transferred", makerspace=space, target=space, meta={
                "new_user_id": person.pk,
                "previous_user_id": previous.user_id if previous else None,
                "previous_outcome": previous_outcome if previous else None,
            })
    if invitation is None:
        return "transferred", None
    from apps.accounts.staff_invitation_delivery import deliver

    return "invited", deliver(*invitation).get("delivery_status")
