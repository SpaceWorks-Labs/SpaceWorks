"""The `event_card` holder kind (SPEC §4.4, §7).

Standing: active and not past its valid-until (event end + 1 day) -> valid; active and
past it -> expired; revoked -> revoked. The event's own card design wins over its
organising organisation's library default, then the space default.
"""
from django.utils import timezone
from django.utils.text import slugify

from apps.card_designs.holders import HolderKind, register as register_kind
from apps.card_designs.holders_member import fmt_date


def standing(card):
    if card.status == "revoked":
        return "revoked"
    return "expired" if card.valid_until <= timezone.now() else "valid"


def _team(card):
    try:
        from .hackathons.team_models import HackathonTeamMember
        row = HackathonTeamMember.objects.filter(event_id=card.event_id, member_id=card.person_id,
                                                 state="active").select_related("team").first()
        return row.team.name if row else ""
    except Exception:
        return ""


def _organisers(event):
    from .models import EventOrganizer
    return list(EventOrganizer.objects.filter(event=event).select_related("organization").order_by("pk"))


def snapshot(card):
    from apps.card_designs import tokens
    event, space = card.event, card.makerspace
    organisers = _organisers(event)
    live = tokens.live("event_card", card)
    return {"name": card.printed_name, "number": f"EV-{card.event_id}-{card.registration_id}",
            "event": event.title, "plan": card.get_role_display(), "role": card.get_role_display(),
            "team": _team(card), "track": "", "space": (space.branding_config or {}).get("display_name") or space.name,
            "organisation": organisers[0].organization.name if organisers else "",
            "valid_until": fmt_date(card.valid_until), "issued_on": fmt_date(card.issued_at),
            "verify_url": tokens.short_url(live.token) if live else ""}


def design(card):
    from apps.card_designs.resolution import resolve
    registration = card.registration
    return resolve(card.makerspace_id, "event_card", event_id=card.event_id,
                   ticket_type_id=registration.ticket_type_id,
                   organization_ids=[row.organization_id for row in _organisers(card.event)])


def issuer(card):
    from apps.inventory import public_image_storage
    return {"kind": "event", "name": card.event.title,
            "logo_url": public_image_storage.public_url(card.makerspace.logo_key) or None}


def logos(card):
    from apps.card_designs.images import read_public_image
    organisers = _organisers(card.event)
    return {"space": read_public_image(card.makerspace.logo_key),
            "event": read_public_image(card.event.image_key),
            "organisation": read_public_image(organisers[0].organization.logo_key) if organisers else None}


def switched_on(card):
    from apps.card_designs.switches import event_cards_on
    return event_cards_on(card.makerspace)


def email(card):
    return card.person.email if card.person_id else ""


def register():
    from apps.card_designs.photos import photo_bytes
    from .models import EventIdCard
    register_kind(HolderKind(
        kind="event_card", model=lambda: EventIdCard, domain="event_card", standing=standing, snapshot=snapshot,
        design=design, account_id=lambda card: card.person_id, switched_on=switched_on,
        # The public check for event cards rides `events.id_cards` itself (SPEC §7).
        public_verify=switched_on, issuer=issuer, photo_bytes=photo_bytes, logos=logos,
        filename=lambda card: slugify(f"{card.event_id}-{card.printed_name}")[:80] or f"event-card-{card.pk}",
        label=lambda card: card.event.title, email=email,
    ))
