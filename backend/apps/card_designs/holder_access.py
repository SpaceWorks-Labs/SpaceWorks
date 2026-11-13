"""The holder's own cards, across every space, programme and event (#132 "My cards").

A card belongs to its holder's account: the member's membership, the linked programme
account, or the registrant. Nothing here takes a makerspace from the client; the card
row names it, and its switch must be on.
"""
from rest_framework.exceptions import NotFound

from .holders import registered

MAX_CARDS = 50


def own_card(user, kind, card_id, *, staff_ok=False):
    """The caller's own card. Staff cards (O-B4) have no photo upload, e-mail or extras, so only the views that
    pass `staff_ok=True` (face, download, check link, wallet) reach one; the rest answer 404."""
    if kind == "staff_card" and not staff_ok:
        raise NotFound()
    spec = registered().get(kind)
    card = spec.model().objects.filter(pk=card_id).first() if spec else None
    if (card is None or spec.account_id(card) != user.pk or not spec.switched_on(card)
            or spec.standing(card) is None):
        raise NotFound()
    return spec, card


def _member_cards(user):
    from apps.makerspaces.models import MemberCard
    return MemberCard.objects.filter(membership__user=user).select_related(
        "makerspace", "membership__assigned_role").order_by("-issued_at")


def _programme_cards(user):
    try:
        from apps.id_programmes.models import IdProgrammeCard
    except Exception:
        return []
    return IdProgrammeCard.objects.filter(user=user, status__in=("approved", "revoked")).select_related(
        "programme__organization", "makerspace").order_by("-issued_at")


def _event_cards(user):
    from apps.events.models import EventIdCard
    return EventIdCard.objects.filter(person=user).select_related("event", "makerspace").order_by("-issued_at")


def _staff_cards(user):
    from .models_staff_cards import StaffCard
    return StaffCard.objects.filter(membership__user=user, revoked_at__isnull=True).select_related(
        "makerspace", "membership__user").order_by("-issued_at")


def my_cards(user):
    sources = {"member_card": _member_cards, "programme_card": _programme_cards, "event_card": _event_cards,
               "staff_card": _staff_cards}
    rows = []
    for kind, source in sources.items():
        spec = registered().get(kind)
        if spec is None:
            continue
        for card in source(user):
            if kind == "member_card" and card.revoked_at is not None and card.membership is None:
                continue
            standing = spec.standing(card) if spec.switched_on(card) else None
            if standing is not None:
                rows.append((kind, spec, card, standing))
    rows.sort(key=lambda row: getattr(row[2], "issued_at", None) or getattr(row[2], "created_at"), reverse=True)
    return rows[:MAX_CARDS]
