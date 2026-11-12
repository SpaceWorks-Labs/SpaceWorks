"""The holders a bulk photo batch can match against, per card kind, and each kind's staff authority (D314c).

`holders(batch)` -> list of dicts (id, name, number, email, has_photo) for the batch's scope: a space's live member
cards, a space's live staff cards (their photo is their member card's), or one event's active ID cards.
`authorise` answers 404 for another tenant and for an actor without the kind's card authority, exactly like the
single-photo routes it reuses (member cards MANAGE_MEMBER_CARDS, staff cards `staff_card_access`, event cards an
organiser of the event).
"""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from django.utils.translation import gettext

MAX_HOLDERS = 5000


def _user_name(user):
    return (user.display_name or user.get_full_name() or user.username) if user else ""


def authorise(actor, kind, makerspace_id, event_id=None):
    """-> (makerspace, event or None); raises 404 / 403 like the matching single-photo route."""
    from apps.makerspaces.models import Makerspace
    if kind == "member_card":
        from apps.accounts import rbac
        from apps.admin_api.views_member_memberships import _makerspace
        from apps.makerspaces.guards import require_module
        space = _makerspace(actor, makerspace_id, rbac.Action.MANAGE_MEMBER_CARDS)
        require_module(space, "membership")
        return space, None
    if kind == "staff_card":
        from .staff_card_access import space_for
        return space_for(actor, makerspace_id), None
    if kind == "event_card":
        from apps.events.id_cards_views import organiser_event
        if not event_id:
            raise ValidationError({"event_id": gettext("Choose the event whose cards these photos are for.")})
        event = organiser_event(actor, event_id)
        if event.makerspace_id != int(makerspace_id):
            raise NotFound()
        return get_object_or_404(Makerspace, pk=event.makerspace_id), event
    raise NotFound()


def _member_cards(space):
    from apps.makerspaces.membership_number import display_number
    from apps.makerspaces.models import MemberCard
    rows = MemberCard.objects.filter(makerspace=space, revoked_at__isnull=True, membership__isnull=False
                                     ).select_related("membership__user")[:MAX_HOLDERS]
    for card in rows:
        membership = card.membership
        number = card.number_text or (display_number(membership) if membership.member_number else str(card.card_number))
        yield {"id": card.pk, "name": card.printed_name or _user_name(membership.user), "number": number,
               "email": membership.user.email or "", "has_photo": bool(card.photo_object_key)}


def _staff_cards(space):
    from apps.makerspaces.models import MemberCard
    from .models_staff_cards import StaffCard
    with_photo = set(MemberCard.objects.filter(makerspace=space, revoked_at__isnull=True).exclude(
        photo_object_key="").values_list("membership_id", flat=True))
    rows = StaffCard.objects.filter(makerspace=space, revoked_at__isnull=True, membership__isnull=False
                                    ).select_related("membership__user")[:MAX_HOLDERS]
    for card in rows:
        user = card.membership.user
        yield {"id": card.pk, "name": _user_name(user), "number": card.number_text or f"S-{card.card_number:04d}",
               "email": user.email or "", "has_photo": card.membership_id in with_photo}


def _event_cards(event):
    from apps.events.models import EventIdCard
    from .holders import spec_for
    spec = spec_for("event_card")
    rows = EventIdCard.objects.filter(event=event, status=EventIdCard.Status.ACTIVE).select_related(
        "person", "registration")[:MAX_HOLDERS]
    for card in rows:
        yield {"id": card.pk, "name": card.printed_name or _user_name(card.person), "number": "",
               "email": spec.email(card) or "", "has_photo": bool(card.photo_object_key)}


def holders(batch, space, event):
    source = {"member_card": lambda: _member_cards(space), "staff_card": lambda: _staff_cards(space),
              "event_card": lambda: _event_cards(event)}[batch.kind]
    return list(source())


def load_card(kind, space, holder_id, event=None):
    """The card row a holder id names, in this batch's scope (None when it is gone or out of scope)."""
    if kind == "member_card":
        from apps.makerspaces.models import MemberCard
        return MemberCard.objects.filter(pk=holder_id, makerspace=space, revoked_at__isnull=True).first()
    if kind == "staff_card":
        from .models_staff_cards import StaffCard
        return StaffCard.objects.filter(pk=holder_id, makerspace=space, revoked_at__isnull=True).first()
    from apps.events.models import EventIdCard
    return EventIdCard.objects.filter(pk=holder_id, event=event, status=EventIdCard.Status.ACTIVE).first()
