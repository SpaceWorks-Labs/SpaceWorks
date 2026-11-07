"""Who may see and edit a card design (SPEC §11, #128, Q-I9). All scoping goes through rbac.

* member cards: `MANAGE_MEMBER_CARDS` in the space (`membership` on).
* ID programmes: `MANAGE_ID_PROGRAMMES` on the host space, including through the
  organisation branch (`membership.id_programmes` on).
* event cards and tickets: EVERY organiser of that event, i.e. anyone holding the
  event's edit permission -- host event staff, co-hosting organisations' members acting
  through `EventOrganizer`, a member assigned as organiser -- and nobody with only a
  check-in, judging, mentoring or volunteer grant (Q-I9). An organisation library
  default and the space-wide event default need `MANAGE_EVENTS`.
"""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac

from .models import CardDesign
from .switches import domain_on

EVENT_DOMAINS = (CardDesign.Domain.EVENT_CARD, CardDesign.Domain.EVENT_TICKET)


def can_edit(actor, design):
    domain = design.domain
    if domain == CardDesign.Domain.MEMBER_CARDS:
        return rbac.can(actor, rbac.Action.MANAGE_MEMBER_CARDS, design.makerspace_id)
    if domain == CardDesign.Domain.ID_PROGRAMME:
        return rbac.can(actor, rbac.Action.MANAGE_ID_PROGRAMMES, design.makerspace_id)
    if design.event_id:
        from apps.events import event_authority
        from apps.events.event_permissions import EDIT_DETAILS
        return event_authority.can(actor, design.event, EDIT_DETAILS)
    return rbac.can(actor, rbac.Action.MANAGE_EVENTS, design.makerspace_id)


def acted_for(actor, design):
    """The organisation an event organiser acted for, when not as host-space staff."""
    if design.domain not in EVENT_DOMAINS or not design.event_id:
        return None
    if rbac.can(actor, rbac.Action.MANAGE_EVENTS, design.makerspace_id):
        return None
    from apps.organizations.models import OrganizationMembership
    row = OrganizationMembership.objects.filter(user=actor, status="active",
                                                organization__organized_events__event_id=design.event_id).first()
    return row.organization_id if row else None


def require_edit(actor, design):
    if not domain_on(design.makerspace, design.domain):
        raise NotFound()
    if not can_edit(actor, design):
        raise PermissionDenied(gettext("You cannot edit this card design."))
    return design


def design_for(actor, pk):
    design = get_object_or_404(CardDesign.objects.select_related("makerspace", "event", "programme"), pk=pk)
    from .approval import can_approve
    if not (can_edit(actor, design) or can_approve(actor, design)):
        # Uniform: a design in a space or event the actor cannot reach does not exist for them.
        raise NotFound()
    if not domain_on(design.makerspace, design.domain):
        raise NotFound()
    return design


def space_for(actor, makerspace_id, action=rbac.Action.MANAGE_MEMBER_CARDS, *, module="membership"):
    from apps.makerspaces.guards import require_module
    from apps.makerspaces.models import Makerspace
    space = get_object_or_404(rbac.scope_by_action(actor, action, Makerspace.objects.all(), field="id"),
                              pk=makerspace_id)
    if module:
        require_module(space, module)
    return space
