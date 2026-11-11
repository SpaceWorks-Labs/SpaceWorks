"""What a desk needs to print badges (parity E-B2): the published design per role, logos, and one row per person.

The same payload feeds the online desk (`GET admin/events/<pk>/badges/desk`), the PIN station and the encrypted
offline roster, so a badge looks identical whichever way it is printed. Nothing here edits a design or rotates a
credential. Roles resolve at event level (role variant, then the event, organisation and space defaults); a
ticket-type specific design is used by the online card render, not by the offline bundle.
"""
import base64

from django.utils import timezone

from apps.card_designs.layout import normalize_document
from apps.card_designs.resolution_roles import ROLES, resolve_event_card

from . import badge_snapshot
from .badge_credentials import current_checkin_payload
from .id_cards_holder import _organisers, team_for
from .models import EventIdCard, EventRegistration

LOGO_MAX_BYTES = 200 * 1024
ATTENDEE = "attendee"
PROVISIONAL = ("waitlisted", "pending_approval")


def _mime(data):
    return "image/jpeg" if data[:2] == bytes((255, 216)) else "image/webp" if data[8:12] == b"WEBP" else "image/png"


def _data_url(data):
    """A small image as a data URL, or None when it is missing or over the 200 KB cap."""
    if not data or len(data) > LOGO_MAX_BYTES:
        return None
    return f"data:{_mime(data)};base64," + base64.b64encode(data).decode("ascii")


def _asset_ids(node):
    """Every design asset a compiled document refers to (image layers, backgrounds, watermarks)."""
    if isinstance(node, dict):
        found = {node["asset_id"]} if node.get("asset_id") else set()
        for value in node.values():
            found |= _asset_ids(value)
        return found
    if isinstance(node, list):
        return set().union(*(_asset_ids(item) for item in node)) if node else set()
    return set()


def _design_assets(event, document):
    """asset id -> data URL (<= 200 KB each), so a free-canvas design prints with no network."""
    from rest_framework.exceptions import NotFound
    from apps.card_designs.assets import read
    found = {}
    for asset_id in sorted(_asset_ids(document)):
        try:
            url = _data_url(read(event.makerspace, asset_id))
        except (NotFound, ValueError):
            url = None
        if url:
            found[asset_id] = url
    return found


def _shows_photo(document):
    return any(layer.get("kind") == "photo" for layer in document.get("front", {}).get("layers", []))


def _photo_url(card):
    from apps.card_designs.photos import photo_bytes
    return _data_url(photo_bytes(card)) if _photo_card_id(card) else None


def role_designs(event):
    """-> ({design key: {...compiled design...}}, {role: design key}, {role: printed tags})."""
    org_ids = [row.organization_id for row in _organisers(event)]
    designs, by_role, tags = {}, {}, {}
    for role in (ATTENDEE, *ROLES):
        document, design = resolve_event_card(event.makerspace_id, event.pk, None, org_ids, role)
        key = str(design.pk) if design is not None else "default"
        if key not in designs:
            normalized = normalize_document(document, check_contrast=False)
            source = normalized.get("source") or {}
            designs[key] = {"design_id": design.pk if design is not None else None,
                            "revision": design.published_revision if design is not None else None,
                            "stock": normalized.get("stock"), "document": normalized,
                            "settings": source.get("settings"), "assets": _design_assets(event, normalized)}
        by_role[role] = key
        tags[role] = badge_snapshot.printed_tags(designs[key]["document"])
    return designs, by_role, tags


def logos(event):
    """Space, event, organisation and sponsor logos as small data URLs (larger ones are left out)."""
    from apps.card_designs.images import read_public_image
    organisers = _organisers(event)
    found = {"space": read_public_image(event.makerspace.logo_key), "event": read_public_image(event.image_key),
             "organisation": read_public_image(organisers[0].organization.logo_key) if organisers else None,
             **badge_snapshot.sponsor_logos(event)}
    return {name: url for name, url in ((name, _data_url(data)) for name, data in found.items()) if url}


def design_bundle(event):
    designs, by_role, _tags = role_designs(event)
    return {"designs": designs, "roles": by_role, "logos": logos(event)}


def _photo_card_id(card):
    return card.pk if card is not None and card.photo_object_key and card.photo_consent_at else None


def rows(event, registrations, *, with_payload=True, cards=None, bundle=None, with_photo=False):
    """One badge row per registration. `bundle` = `role_designs(event)`; reuse it across batches."""
    designs, by_role, tags = bundle or role_designs(event)
    registrations = list(registrations)
    ids = [registration.pk for registration in registrations]
    if cards is None:
        cards = {card.registration_id: card for card in EventIdCard.objects.filter(
            event=event, registration_id__in=ids, status=EventIdCard.Status.ACTIVE)}
    from .contributions.crew_reads import crew_labels
    crew = crew_labels(event, ids)
    form = badge_snapshot.allowed_keys(event)
    result = []
    for registration in registrations:
        card = cards.get(registration.pk)
        role = card.role if card is not None else ATTENDEE
        wanted = tags.get(role) or tags[ATTENDEE]
        values = badge_snapshot.projection(event, registration, wanted, crew=crew.get(registration.pk, ""), form=form)
        team = team_for(event.pk, registration.member_id)[0] if "team" in wanted else ""
        row = {"registration_id": registration.pk, "card_id": card.pk if card is not None else None,
               "name": card.printed_name if card is not None else registration.name, "role": role,
               "role_label": card.get_role_display() if card is not None else EventIdCard.Role(role).label,
               "team": team, "crew_kind": values.pop("crew_kind", ""), "email": values.pop("email", None),
               "answers": values, "photo_card_id": _photo_card_id(card),
               "provisional": registration.status in PROVISIONAL, "status": registration.status}
        if row["email"] is None:
            del row["email"]
        if with_photo and _shows_photo(designs[by_role.get(role) or by_role[ATTENDEE]]["document"]):
            row["photo"] = _photo_url(card)
        if with_payload:
            row["checkin_payload"] = current_checkin_payload(registration)
        result.append(row)
    return result


STATUS_SETS = ("confirmed", "attendees_without_crew", "crew", "checked_in", "not_checked_in", "all")


def status_set_rows(event, status_set, limit=500):
    """Registrations a status set prints: `all` adds the waitlisted and pending (provisional badges)."""
    queryset = EventRegistration.objects.filter(event=event)
    confirmed = queryset.filter(status__in=("registered", "attended"))
    if status_set == "all":
        queryset = queryset.filter(status__in=("registered", "attended", *PROVISIONAL))
    elif status_set == "checked_in":
        queryset = confirmed.filter(status="attended")
    elif status_set == "not_checked_in":
        queryset = confirmed.filter(status="registered")
    elif status_set in ("crew", "attendees_without_crew"):
        crew_ids = list(confirmed.filter(is_crew=True).values_list("pk", flat=True))
        queryset = confirmed.filter(pk__in=crew_ids) if status_set == "crew" else confirmed.exclude(pk__in=crew_ids)
    else:
        queryset = confirmed
    return list(queryset.select_related("event__makerspace").order_by("created_at", "pk")[:limit])


def desk_payload(event, *, registration=None, status_set=None):
    bundle = role_designs(event)
    designs, by_role, _tags = bundle
    payload = {"event": {"id": event.pk, "title": event.title}, "server_time": timezone.now(),
               "designs": designs, "roles": by_role, "logos": logos(event)}
    if registration is not None:
        payload["badge"] = rows(event, [registration], bundle=bundle, with_photo=True)[0]
    if status_set:
        payload["badges"] = rows(event, status_set_rows(event, status_set), bundle=bundle, with_photo=True)
    return payload
