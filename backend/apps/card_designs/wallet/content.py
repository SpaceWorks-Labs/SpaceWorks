"""What a wallet pass shows (SPEC §8.2): issuer, holder name, number, plan/programme/
event, valid-until and the QR. Never a photo, never the sensitive extras.

The QR is the desk QR for member cards and the public check link otherwise. A digest
of this content tells the refresh sweep when a pass must be updated.
"""
import hashlib
import json

from ..holders import spec_for

LABELS = {"member_card": "Plan", "programme_card": "Programme", "event_card": "Event"}


def pass_content(kind, card):
    from .. import tokens
    spec = spec_for(kind)
    values = spec.snapshot(card)
    issuer = spec.issuer(card)
    token = tokens.live(kind, card)
    qr = spec.desk_payload(card) if kind == "member_card" else (tokens.url(token.token) if token else "")
    label_value = {"member_card": values.get("plan"), "programme_card": values.get("programme"),
                   "event_card": values.get("event")}[kind] or ""
    return {
        "issuer": issuer["name"], "name": values.get("name", ""), "number": values.get("number", ""),
        "label": LABELS[kind], "label_value": label_value, "valid_until": values.get("valid_until", ""),
        "qr": qr or "", "standing": spec.standing(card) or "revoked",
    }


def content_digest(content):
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
