"""Turn a scanned code into a holder card -- for STAFF desks only (#132, Q-I10).

A scan identifies; it never authenticates (Q-I10): nothing here signs anyone in, and
member self-checkout still needs the member's own session. Accepted codes: a member
card's desk QR (32 hex), or any card's check link / bare 43-char token. Lookups are
always confined to one space, so a code from another tenant simply finds nothing.
"""
import re

from .holders import registered
from .models import CardVerifyToken
from .tokens import SHAPE

DESK = re.compile(r"^[0-9a-f]{32}$")
LINK = re.compile(r"/verify/c/([A-Za-z0-9_-]{43})/?$")


def token_from(payload):
    payload = (payload or "").strip()
    match = LINK.search(payload)
    if match:
        return match.group(1)
    return payload if SHAPE.match(payload) else None


def live_holder(makerspace_id, payload):
    """(kind, card) for a live check token scanned in this space, else (None, None)."""
    token = token_from(payload)
    if token is None:
        return None, None
    row = CardVerifyToken.objects.filter(token=token, makerspace_id=makerspace_id, retired_at__isnull=True).first()
    if row is None or row.holder_kind not in registered():
        return None, None
    spec = registered()[row.holder_kind]
    return row.holder_kind, spec.model().objects.filter(pk=row.holder_id).first()


def desk_payload_for(makerspace, payload):
    """A member card's desk payload for a scanned check link; other input unchanged."""
    kind, card = live_holder(makerspace.pk, payload)
    if kind == "member_card" and card is not None:
        from apps.makerspaces.member_card_services import active_qr
        qr = active_qr(card)
        if qr is not None:
            return qr.payload
    return (payload or "").strip()


def person_for(makerspace, payload, *, actor=None):
    """The account behind a scanned member card (desk QR or check link) in this space."""
    from apps.boxes.models import QrCode
    from apps.makerspaces.models import MemberCard
    payload = desk_payload_for(makerspace, payload)
    if not DESK.match(payload):
        kind, card = live_holder(makerspace.pk, payload)
        if card is None:
            return None, None
        spec = registered()[kind]
        return spec.account_id(card), card
    qr = QrCode.objects.filter(payload=payload, makerspace=makerspace, target_type=QrCode.TargetType.MEMBER_CARD,
                               status=QrCode.Status.ACTIVE).first()
    if qr is None:
        return None, None
    if actor is not None:
        from apps.boxes.models import QrScanEvent
        QrScanEvent.objects.create(makerspace=makerspace, qr_code=qr, actor=actor,
                                   context=QrScanEvent.Context.MEMBER_LOOKUP)
    card = MemberCard.objects.select_related("membership").filter(pk=qr.target_id, makerspace=makerspace).first()
    if card is None or not card.is_active:
        return None, None
    return card.membership.user_id, card
