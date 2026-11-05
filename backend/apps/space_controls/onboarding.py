"""Onboarding end to end: approve a hosting request, create the space, invite its
Space Manager (#185 item 5). No trial: plans were declined (#185) and the managed
limiter's optional trial is a separate, off-by-default switch (#187A).

Every state change still goes through ``hosting_requests.workflow`` (accept and the
makerspace link); the space itself is created exactly as the /control/ add form does it
(a ``Makerspace`` save, then ``assign_owner_organization``), so its signals seed the
default roles and its owner rules apply. All of it commits together.
"""

from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.hosting_requests import workflow
from apps.hosting_requests.applicant import require_superadmin
from apps.hosting_requests.exceptions import HostingRequestConflict
from apps.hosting_requests.models import HostingRequest
from apps.hosting_requests.prefill import join_organization
from apps.makerspaces.models import Makerspace

from .write_policy import control_context

S = HostingRequest.Status


def _owner(row, organization_id, new_organization_name):
    if organization_id and new_organization_name:
        raise ValidationError({"organization_id": "Choose an existing organization or a new name, not both."})
    if organization_id or new_organization_name:
        return organization_id, (new_organization_name or None)
    joined = join_organization(row)
    if joined is not None:
        return joined.pk, None
    if row.organization_choice == HostingRequest.OrganizationChoice.JOIN:
        raise ValidationError({"organization_id": "The inviting organization is no longer active; choose an owner."})
    return None, (row.new_organization_name or row.space_name)


def approve(actor, request_id, *, name="", slug="", organization_id=None, new_organization_name="",
            invite_manager=True):
    """Returns ``(request, makerspace, invitation_status)``."""
    from apps.organizations.services_owner import assign_owner_organization

    require_superadmin(actor)
    invitation = None
    with transaction.atomic(), control_context():
        row = HostingRequest.objects.select_for_update().get(pk=request_id)
        if row.status == S.SUBMITTED:
            row = workflow.accept(actor, row.pk)
        elif row.status != S.ACCEPTED or row.created_makerspace_id is not None:
            raise HostingRequestConflict()
        name = str(name or row.space_name).strip()[:200]
        slug = slugify(str(slug or row.proposed_slug or name))[:50]
        if not slug:
            raise ValidationError({"slug": "Enter a web address name for the space."})
        if Makerspace.objects.filter(slug=slug).exists():
            raise ValidationError({"slug": "This web address name is already taken."})
        owner_id, owner_name = _owner(row, organization_id, str(new_organization_name or "").strip())
        space = Makerspace.objects.create(name=name, slug=slug, location=row.location, created_by=actor)
        audit.record(actor, "makerspace.created", makerspace=space, target=space, meta={"via": "onboarding"})
        assign_owner_organization(actor, space.pk, organization_id=owner_id, new_name=owner_name)
        workflow.link_created_makerspace(actor, row.pk, space)
        if invite_manager and row.applicant_email:
            invitation = _invite(actor, space, row.applicant_email)
        audit.record(actor, "space_control.space_onboarded", makerspace=space, target=space, meta={
            "hosting_request_id": row.pk, "manager_invited": invitation is not None,
        })
    status = "skipped"
    if invitation is not None:
        from apps.accounts.staff_invitation_delivery import deliver
        status = deliver(*invitation).get("delivery_status") or "unavailable"
    row.refresh_from_db()
    return row, space, status


def _invite(actor, space, email):
    """A hosted space needs mail for its manager's invitation, so Email is turned on."""
    from apps.accounts.services_staff_invitations import issue, onboarding_available
    from apps.makerspaces.module_install import install_module

    if "email" not in set(space.enabled_modules or []):
        install_module(space, "email", actor)
        space.refresh_from_db()
    if not onboarding_available(space):
        return None
    return issue(actor, space.pk, email=email, roles=["space_manager"])
