"""Organization membership governance and deletion with durable reference protection."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.staff_identity import is_person
from apps.accounts import rbac
from apps.admin_api.permissions import active_user
from apps.audit import services as audit
from apps.organizations import governance
from apps.organizations.access import is_superadmin, lock_governance_membership
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_invitations import _authority_actions, _clean_actions


def assert_governor_remains(organization, *, replaced_id, status=None, actions=None, deleting=False):
    """Legacy governorless organizations can be repaired; an existing governor cannot be lost."""
    members = list(organization.memberships.select_for_update(of=("self",))
                   .select_related("user").order_by("pk"))
    governors = [row for row in members if
                 governance.MANAGE_ORGANIZATION_MEMBERS in governance.actions_for_membership(row)]
    target = next((row for row in governors if row.pk == replaced_id), None)
    if target is None or len(governors) > 1:
        return
    remaining = not deleting and (
        (status or target.status) == OrganizationMembership.Status.ACTIVE
        and governance.MANAGE_ORGANIZATION_MEMBERS in (
            target.governance_actions if actions is None else actions
        )
    )
    if not remaining:
        raise OrganizationConflict("Invite another governor before removing the last governor.")


def assert_deletable(organization):
    # Enumerate concrete reverse FKs instead of importing separable domains. This
    # protects future references as well as tenant links and event organizers.
    disposable = {"organizations.OrganizationMembership", "organizations.OrganizationInvitation",
                  "organizations.OrganizationPublicPage", "organizations.OrganizationPublicPageStorage",
                  "makerspaces.PublicHandle", "makerspaces.PublicHandleRedirect",
                  "organizations.OrganizationLeaveReceipt"}
    for relation in organization._meta.related_objects:
        if relation.related_model._meta.label in disposable:
            continue
        if relation.related_model._default_manager.filter(
            **{relation.field.name: organization.pk}
        ).exists():
            raise OrganizationConflict(
                "This organization still has linked makerspaces or retained domain references."
            )
    if organization.logo_key:
        raise OrganizationConflict("Remove organization artwork through platform support before deletion.")


@transaction.atomic
def self_departure(organization, *, user):
    """Internal account-deletion departure; an ordinary member may leave itself.

    Stage A already holds organizations in ascending order before its User lock.
    Reacquiring that same Organization row is safe and also makes this operation
    safe for direct internal callers. No caller-controlled membership ID or actor
    may select another person's authority.
    """
    if not is_person(user):
        raise PermissionDenied("Only member accounts hold organization memberships.")
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    target = locked.memberships.select_for_update().filter(user_id=user.pk).first()
    if target is None or target.status == OrganizationMembership.Status.SUSPENDED:
        return target
    assert_governor_remains(
        locked, replaced_id=target.pk, status=OrganizationMembership.Status.SUSPENDED,
    )
    target.status = OrganizationMembership.Status.SUSPENDED
    target.save(update_fields=["status", "updated_at"])
    audit.record(user, "organization.member_departed", target=target,
                 meta={"status": target.status})
    return target


@transaction.atomic
def update_membership(organization, membership_id, *, actor, **changes):
    unknown = set(changes) - {"status", "governance_actions", "granted_actions"}
    if unknown:
        raise ValidationError({field: "This field cannot be edited." for field in unknown})
    if "status" in changes and changes["status"] not in OrganizationMembership.Status.values:
        raise ValidationError({"status": "Unknown membership status."})
    if not active_user(actor):
        raise PermissionDenied()
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    held = lock_governance_membership(actor, locked, governance.MANAGE_ORGANIZATION_MEMBERS)
    target = get_object_or_404(locked.memberships.select_for_update(), pk=membership_id)
    held_governance, held_grants = _authority_actions(actor, held)
    for field, allowed, possessed in (
        ("governance_actions", governance.GOVERNANCE_ACTIONS, held_governance),
        ("granted_actions", rbac.ORGANIZATION_GRANTABLE_ACTIONS, held_grants),
    ):
        if field in changes:
            proposed = _clean_actions(changes[field], allowed, field)
            # A governor can revoke authority they lack, but cannot confer it.
            additions = set(proposed) - set(getattr(target, field) or [])
            if not additions.issubset(possessed):
                raise PermissionDenied("You cannot grant authority you do not hold.")
            changes[field] = proposed
    if (target.status == OrganizationMembership.Status.SUSPENDED
            and changes.get("status") == OrganizationMembership.Status.ACTIVE):
        if (not set(changes.get("governance_actions", target.governance_actions)).issubset(held_governance)
                or not set(changes.get("granted_actions", target.granted_actions)).issubset(held_grants)):
            raise PermissionDenied("You cannot reactivate authority you do not hold.")
    assert_governor_remains(
        locked, replaced_id=target.pk, status=changes.get("status"),
        actions=changes.get("governance_actions"),
    )
    changed = [field for field, value in changes.items() if getattr(target, field) != value]
    for field in changed:
        setattr(target, field, changes[field])
    if changed:
        target.save(update_fields=[*changed, "updated_at"])
        audit.record(actor, "organization.membership_updated", target=target,
                     meta={"fields": sorted(changed), "status": target.status})
    return target


@transaction.atomic
def delete_organization(organization, *, actor):
    if not active_user(actor):
        raise PermissionDenied()
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    lock_governance_membership(actor, locked, governance.MANAGE_ORGANIZATION_MEMBERS)
    if not is_superadmin(actor):
        lock_governance_membership(actor, locked, governance.MANAGE_ORGANIZATION_PROFILE)
    assert_deletable(locked)
    audit.record(actor, "organization.deleted", target=locked,
                 meta={"membership_count": locked.memberships.count(),
                       "invitation_count": locked.invitations.count()})
    from django.db import connection
    from django.utils import timezone
    from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
    from .models_public_pages import OrganizationPublicPageAsset
    for asset in OrganizationPublicPageAsset.objects.filter(page__organization=locked):
        PublicPageObjectCleanup.objects.update_or_create(object_key=asset.object_key, defaults={
            "owner_kind": "organization", "owner_id": locked.pk, "page_id": asset.page_id,
            "size_bytes": asset.size_bytes, "due_at": timezone.now(), "completed_at": None})
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.allow_immutable_delete', true)")
        previous = cursor.fetchone()[0] or "off"
        cursor.execute("SELECT set_config('app.allow_immutable_delete', 'on', true)")
        locked.delete()
        cursor.execute("SELECT set_config('app.allow_immutable_delete', %s, true)", [previous])
