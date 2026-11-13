"""Who may use space templates: anyone who may manage member cards, ID programmes or events in the space.

Cross-space is 404 (the space is looked up through `scope_by_action`); a design-bound step (save from a design,
apply to a design) additionally needs `authority.can_edit` on that design.
"""
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac

ACTIONS = (rbac.Action.MANAGE_MEMBER_CARDS, rbac.Action.MANAGE_ID_PROGRAMMES, rbac.Action.MANAGE_EVENTS)


def space_for(actor, makerspace_id):
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not any(rbac.can(actor, action, space.pk) for action in ACTIONS):
        raise NotFound()
    return space


def row_for(actor, pk):
    from .models import CardTemplate
    row = get_object_or_404(CardTemplate.objects.select_related("makerspace"), pk=pk)
    return space_for(actor, row.makerspace_id), row


def design_in_space(actor, space, design_id):
    from .authority import can_edit
    from .models import CardDesign
    design = get_object_or_404(CardDesign, pk=design_id, makerspace=space)
    if not can_edit(actor, design):
        raise PermissionDenied(gettext("You cannot edit this card design."))
    return design
