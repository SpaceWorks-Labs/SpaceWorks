"""Decision 295: approve a hosting request and create its space in one transaction.

    submitted (or accepted, no space yet) -> accepted + space + owner organization + governor
    invitations, all or nothing

The space gets the request's kind (makerspace | organization). The owner organization is the
inviting one when the applicant chose to join it, otherwise a new organization (approved:
this superadmin review IS the organization review of decision 292, so nothing is left
pending). The requester is the owner governor: an organization governor invitation and a
Space Manager staff invitation go to the address they confirmed, because one account per
person means they accept those links signed in to their own account. State transitions stay
in ``workflow``; this module only creates the space and links it back.
"""

from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.audit import services as audit
from apps.hosting_requests import notifications, prefill, workflow
from apps.hosting_requests.applicant import require_superadmin
from apps.hosting_requests.exceptions import HostingRequestConflict
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.makerspaces.space_kind import apply_kind_defaults

S = HostingRequest.Status
MANAGER_ROLE = "space_manager"


def _free_slug(row):
    base = (row.proposed_slug or slugify(row.space_name))[:44] or "space"
    candidate, n = base, 2
    while Makerspace.objects.filter(slug__iexact=candidate).exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _create_space(actor, row):
    space = Makerspace.objects.create(
        name=row.space_name, slug=_free_slug(row), location=row.location, kind=row.requested_kind,
        created_by=actor,
    )
    audit.record(actor, "makerspace.created", makerspace=space, target=space,
                 meta={"kind": space.kind, "hosting_request_id": row.pk})
    return apply_kind_defaults(actor, space)


def _owner(actor, space, row):
    from apps.organizations.services_owner import assign_owner_organization
    joined = prefill.join_organization(row)
    if joined is not None:
        return assign_owner_organization(actor, space.pk, organization_id=joined.pk)
    return assign_owner_organization(
        actor, space.pk, new_name=row.new_organization_name or row.space_name,
    )


def _invite_governor(actor, space, organization, row):
    """The requester becomes owner governor once they accept (both links go to them only)."""
    from apps.accounts.services_staff_invitations import issue
    from apps.accounts.staff_invitation_delivery import deliver
    from apps.organizations import governance
    from apps.organizations.services_invitations import create_invitation
    create_invitation(
        organization, actor=actor, governance_actions=sorted(governance.GOVERNANCE_ACTIONS),
        granted_actions=sorted(rbac.ORGANIZATION_GRANTABLE_ACTIONS), invitee_email=row.applicant_email,
    )
    invitation, raw = issue(actor, space.pk, email=row.applicant_email, roles=[MANAGER_ROLE])
    transaction.on_commit(lambda: deliver(invitation, raw))


@transaction.atomic
def approve_and_create(actor, row_id):
    """Returns ``(request, space)``; any failure rolls back the whole approval."""
    require_superadmin(actor)
    row = HostingRequest.objects.select_for_update().filter(pk=row_id).first()
    if row is None:
        raise HostingRequestConflict()
    if row.created_makerspace_id is not None:
        raise HostingRequestConflict(gettext("A space was already created from this request."))
    if not row.applicant_email:
        raise ValidationError({"detail": gettext("This request has no applicant address to invite.")})
    if row.status == S.SUBMITTED:
        workflow.accept(actor, row.pk, notify=False)
    elif row.status != S.ACCEPTED:
        raise HostingRequestConflict()
    space = _create_space(actor, row)
    link = _owner(actor, space, row)
    workflow.link_created_makerspace(actor, row.pk, space)
    _invite_governor(actor, space, link.organization, row)
    row.refresh_from_db()
    notifications.schedule_created(row, space)
    return row, space
