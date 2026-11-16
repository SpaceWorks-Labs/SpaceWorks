"""Staff search sources for the organizer, audience and partner pickers.

Both directories are read-only lookups for people who run events. Neither reveals
anything a staff account could not already see elsewhere: organizations appear only
when they opted into discovery (or the actor already belongs to them), and partner
makerspaces are the central public directory plus spaces the actor already manages.
"""

from django.utils.translation import gettext
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.organizations.models import Organization, OrganizationMembership

from .organizer_authority import _is_superadmin


def _manages_events_somewhere(actor):
    tenant = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, Makerspace.objects.all(), field="id")
    if tenant.exists():
        return True
    memberships = OrganizationMembership.objects.filter(
        user=actor, status=OrganizationMembership.Status.ACTIVE, organization__is_active=True,
    ).select_related("organization")
    return any(rbac.Action.MANAGE_EVENTS in rbac.actions_for_organization_membership(row)
               for row in memberships)


def require_event_staff(actor):
    """Only people who can run events somewhere may search these directories."""
    if _is_superadmin(actor) or _manages_events_somewhere(actor):
        return
    raise PermissionDenied(gettext("Event management access is required."))


def discoverable_organizations(actor):
    rows = Organization.objects.filter(is_active=True)
    if _is_superadmin(actor):
        return rows
    member_of = OrganizationMembership.objects.filter(
        user=actor, status=OrganizationMembership.Status.ACTIVE,
    ).values("organization_id")
    return rows.filter(Q(is_discoverable=True) | Q(pk__in=member_of))


def partner_makerspaces(actor):
    managed = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, Makerspace.objects.all(), field="id")
    listed = Q(public_site_enabled=True, hidden_from_central_directory=False)
    # A partner must run events itself to accept the invitation, so others are noise.
    return servable_queryset(Makerspace.objects.filter(
        listed | Q(pk__in=managed.values("pk")), enabled_modules__contains=["events"],
    ))


def host_makerspaces(actor, request=None):
    """Spaces this actor may HOST a new event in (DY-63): event authority there, events on.

    A request from a space's own staff origin can only host in that space, exactly as a
    URL-scoped route from that origin would be (origin scoping, CLAUDE.md invariants).
    """
    rows = servable_queryset(rbac.scope_by_action(
        actor, rbac.Action.MANAGE_EVENTS, Makerspace.objects.filter(enabled_modules__contains=["events"]),
        field="id"))
    if request is not None:
        from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
        scoped = origin_scoped_makerspace_id(request)
        if scoped is not None:
            rows = rows.filter(pk=scoped)
    return rows.order_by("name", "id")


def require_host(actor, request, makerspace_id):
    """The chosen host space, or 403 when the actor cannot host events there."""
    host = host_makerspaces(actor, request).filter(pk=makerspace_id).first()
    if host is None:
        raise PermissionDenied(gettext("You cannot host events in that makerspace."))
    return host


def search(queryset, term):
    term = (term or "").strip()[:100]
    if term:
        queryset = queryset.filter(Q(name__icontains=term) | Q(slug__icontains=term))
    return queryset.order_by("name", "id")
