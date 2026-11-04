"""One interface over the three holder kinds (SPEC §0.1 item 1).

`member_card` (makerspaces.MemberCard), `programme_card` (id_programmes.IdProgrammeCard)
and `event_card` (events.EventIdCard) each register a `HolderKind` from their own app.
The engine -- rendering, verify, tokens, jobs, email, wallet passes, extras -- only
ever talks to this interface, so the separable apps can be tombstoned without
breaking it. A tombstoned kind is simply not registered: its cards read as not found.
"""
from dataclasses import dataclass
from typing import Callable

from rest_framework.exceptions import NotFound

KINDS = ("member_card", "programme_card", "event_card")


@dataclass(frozen=True)
class HolderKind:
    kind: str
    model: Callable            # () -> model class
    domain: str                # CardDesign.Domain value
    # Live standing for verify/My cards: "valid" | "expired" | "revoked" | None (= hidden, 404).
    standing: Callable
    snapshot: Callable         # (card) -> dict of data-field values (never sensitive extras)
    design: Callable           # (card) -> CardDesign or None (the resolved, published design)
    account_id: Callable       # (card) -> the holder's user id or None
    switched_on: Callable      # (card) -> bool: the governing module / capability is on
    public_verify: Callable    # (card) -> bool: the space/programme/event allows the public check
    issuer: Callable           # (card) -> {"kind", "name", "logo_url"}
    photo_bytes: Callable      # (card) -> bytes or None
    logos: Callable            # (card) -> {"space": bytes, "organisation": bytes, "event": bytes, "symbol": bytes}
    filename: Callable         # (card) -> safe base filename, e.g. "TNK-0042-priya-raman"
    desk_payload: Callable = lambda card: None
    label: Callable = lambda card: ""           # plan / programme / event name for lists
    redact: Callable = lambda card: None        # erase name/photo on revoke or erasure
    email: Callable = lambda card: ""           # the address "your card" mail goes to


_KINDS = {}


def register(spec):
    if spec.kind not in KINDS:
        raise ValueError("Unknown holder kind")
    existing = _KINDS.get(spec.kind)
    if existing is not None and existing != spec:
        raise ValueError("Duplicate holder kind")
    _KINDS[spec.kind] = spec


def spec_for(kind):
    spec = _KINDS.get(kind)
    if spec is None:
        raise NotFound()
    return spec


def registered():
    return dict(_KINDS)


def load(kind, card_id):
    spec = spec_for(kind)
    card = spec.model().objects.filter(pk=card_id).first()
    if card is None:
        raise NotFound()
    return spec, card


def holder_filter(kind, card):
    """Keyword filter for the HolderCardMixin rows hanging off this card."""
    if kind not in KINDS:
        raise NotFound()
    return {kind: card}
