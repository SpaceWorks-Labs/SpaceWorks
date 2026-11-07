"""Authority for ID programmes (SPEC §11): actions on the HOST space, through rbac only.

`MANAGE_ID_PROGRAMMES` (implies `VIEW_ID_PROGRAMMES`) is held by the Space Manager and is
grantable to custom roles and through the organisation branch, so organisation
governors run programmes without a space role. No new scoping axis: every programme
query is `rbac.scope_by_action` on the host makerspace. The capability
`membership.id_programmes` must be on, or every route is 404.
"""
from django.utils.translation import gettext
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.card_designs.switches import programmes_on

from .models import IdProgramme, IdProgrammeCard

VIEW, MANAGE = rbac.Action.VIEW_ID_PROGRAMMES, rbac.Action.MANAGE_ID_PROGRAMMES


def programmes_for(actor, action=VIEW):
    return rbac.scope_by_action(actor, action, IdProgramme.objects.select_related("organization", "makerspace"))


def programme_for(actor, pk, action=VIEW):
    programme = get_object_or_404(programmes_for(actor, VIEW), pk=pk)
    if not programmes_on(programme.makerspace):
        raise Http404
    if action == MANAGE and not rbac.can(actor, MANAGE, programme.makerspace_id):
        raise PermissionDenied(gettext("You can view this programme but not change it."))
    return programme


def card_for(actor, pk, action=VIEW):
    card = get_object_or_404(rbac.scope_by_action(actor, VIEW, IdProgrammeCard.objects.select_related(
        "programme__organization", "makerspace")), pk=pk)
    if not programmes_on(card.makerspace):
        raise Http404
    if action == MANAGE and not rbac.can(actor, MANAGE, card.makerspace_id):
        raise PermissionDenied(gettext("You can view this card but not change it."))
    return card


def can_manage(actor, programme):
    return rbac.can(actor, MANAGE, programme.makerspace_id)
