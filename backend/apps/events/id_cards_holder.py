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
    """-> (team name, track names). The track comes from the team's submission (a hackathon
    entry may enter several tracks); a person with no team or no submission prints neither."""
    return team_for(card.event_id, card.person_id)


def team_for(event_id, member_id):
    """The same, for an event and a member (the offline roster has registrations that hold no card)."""
    if not member_id:
        return "", ""
    try:
        from .hackathons.team_models import HackathonTeamMember
        row = HackathonTeamMember.objects.filter(event_id=event_id, member_id=member_id,
                                                 state="active").select_related("team").first()
    except Exception:
        return "", ""
    if row is None:
        return "", ""
    return row.team.name, _tracks(row.team)


def _tracks(team):
    try:
        from .judging.models_definitions import HackathonTrack
        submission = getattr(team, "submission", None)
        ids = [value for value in (submission.track_ids if submission else []) if isinstance(value, int)]
        names = HackathonTrack.objects.filter(event_id=team.event_id, pk__in=ids).order_by("order", "pk")
        return " · ".join(names.values_list("name", flat=True)[:3])
    except Exception:
        return ""


def _organisers(event):
    from .models import EventOrganizer
    return list(EventOrganizer.objects.filter(event=event).select_related("organization").order_by("pk"))


def resolved_design(card):
    """-> (document, design) for this card's role, once per card instance (snapshot and logos both read it)."""
    cached = getattr(card, "_resolved_design", None)
    if cached is None:
        cached = card._resolved_design = _resolve(card)
    return cached


def _printed_tags(card):
    from .badge_snapshot import printed_tags
    try:
        return printed_tags(resolved_design(card)[0])
    except (KeyError, TypeError, AttributeError):
        return set()


def snapshot(card):
    from apps.card_designs import tokens
    from .badge_snapshot import projection
    event, space = card.event, card.makerspace
    organisers = _organisers(event)
    live = tokens.live("event_card", card)
    team, track = _team(card)
    return {**projection(event, card.registration, _printed_tags(card)), "name": card.printed_name,
            "number": f"EV-{card.event_id}-{card.registration_id}",
            "event": event.title, "plan": card.get_role_display(), "role": card.get_role_display(),
            "team": team, "track": track, "space": (space.branding_config or {}).get("display_name") or space.name,
            "organisation": organisers[0].organization.name if organisers else "",
            "valid_until": fmt_date(card.valid_until), "issued_on": fmt_date(card.issued_at),
            "verify_url": tokens.short_url(live.token) if live else ""}


def _resolve(card):
    from apps.card_designs.resolution_roles import resolve_event_card
    registration = card.registration
    return resolve_event_card(card.makerspace_id, card.event_id, registration.ticket_type_id,
                              [row.organization_id for row in _organisers(card.event)], card.role)


def design(card):
    """The resolved design: the holder's role variant first (E-B1), then the usual event, organisation, space chain."""
    return resolved_design(card)


def issuer(card):
    from apps.inventory import public_image_storage
    return {"kind": "event", "name": card.event.title,
            "logo_url": public_image_storage.public_url(card.makerspace.logo_key) or None}


def logos(card):
    from apps.card_designs.images import read_public_image
    organisers = _organisers(card.event)
    result = {"space": read_public_image(card.makerspace.logo_key),
              "event": read_public_image(card.event.image_key),
              "organisation": read_public_image(organisers[0].organization.logo_key) if organisers else None}
    if _wants_sponsors(card):
        from .badge_snapshot import sponsor_logos
        result.update(sponsor_logos(card.event))
    return result


def _wants_sponsors(card):
    try:
        document = resolved_design(card)[0]
        return any(layer.get("source", "").startswith("sponsor_")
                   for side in ("front", "back") for layer in document[side]["layers"] if layer["kind"] == "logo")
    except (KeyError, TypeError, AttributeError):
        return False


def checkin_payload(card):
    """The registration's check-in code for the `checkin_qr` layer; None (a placeholder) when none is live."""
    from .badge_credentials import current_checkin_payload
    return current_checkin_payload(card.registration)


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
        checkin_payload=checkin_payload,
        filename=lambda card: slugify(f"{card.event_id}-{card.printed_name}")[:80] or f"event-card-{card.pk}",
        label=lambda card: card.event.title, email=email,
    ))
