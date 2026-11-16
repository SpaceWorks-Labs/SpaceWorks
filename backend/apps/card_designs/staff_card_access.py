"""Who may reach the staff-card routes, and the serialised shapes they return (O-B4 part 2).

Cross-tenant and unauthorised both answer 404 (a space or card the actor cannot manage does not exist for
them). The surface is gated by module `membership` + capability `membership.staff_cards` (typed 404 when off).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import Makerspace

from . import tokens
from .lifecycle import public_verify_on
from .models_staff_cards import StaffCard
from .staff_card_roles import held_roles, machine_scope_text, role_name, role_slugs
from .staff_card_services import can_manage, eligible


def space_for(actor, makerspace_id):
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    if not can_manage(actor, space.pk):
        raise Http404()
    require_membership_feature(space, "staff_cards")
    return space


def card_for(actor, pk):
    card = get_object_or_404(StaffCard.objects.select_related("makerspace", "membership__user"), pk=pk)
    space_for(actor, card.makerspace_id)
    return card


def card_row(card):
    from .holders import registered
    spec = registered()["staff_card"]
    token = tokens.live("staff_card", card) if card.is_active else None
    return {"id": card.pk, "number": card.number_text or f"S-{card.card_number:04d}",
            "status": spec.standing(card), "issued_at": card.issued_at, "revoked_at": card.revoked_at,
            "revoked_reason": card.revoked_reason, "print_count": card.print_count,
            "check_url": tokens.url(token.token) if token and public_verify_on("staff_card", card) else "",
            "roles_changed_since_issue": bool(card.is_active and card.membership_id
                                              and sorted(card.roles or []) != sorted(role_slugs(card.membership)))}


def holder_row(membership, card):
    user = membership.user
    roles = held_roles(membership)
    return {"membership_id": membership.pk, "name": user.display_name or user.get_full_name() or user.username,
            "roles": [{"slug": role.slug, "name": role_name(role)} for role in roles],
            "roles_text": ", ".join(role_name(role) for role in roles),
            "machine_scope": machine_scope_text(membership), "eligible": eligible(membership),
            "card": card_row(card) if card else None}
