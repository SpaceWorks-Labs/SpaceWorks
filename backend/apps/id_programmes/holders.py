"""The `programme_card` holder kind (SPEC §4.3, §7).

Standing: approved and in date -> valid; approved and past `expires_at` -> expired;
revoked -> revoked; pending or rejected -> hidden (the public check answers 404).
"""
import json

from django.utils import timezone
from django.utils.text import slugify

from apps.card_designs.holders import HolderKind, register as register_kind
from apps.card_designs.holders_member import fmt_date


def standing(card):
    if card.status == "revoked":
        return "revoked"
    if card.status != "approved":
        return None
    if card.expires_at and card.expires_at <= timezone.now():
        return "expired"
    return "valid"


def answers(card):
    try:
        value = json.loads(card.answers or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def snapshot(card):
    from apps.card_designs import tokens
    programme = card.programme
    space = card.makerspace
    placed = {question.get("key") for question in programme.form_schema or ()
              if isinstance(question, dict) and question.get("placement") in ("front", "back")}
    values = {
        "name": card.name, "number": card.id_number or "", "programme": programme.name,
        "plan": programme.name, "organisation": programme.organization.name,
        "space": (space.branding_config or {}).get("display_name") or space.name,
        "valid_until": fmt_date(card.expires_at) if card.expires_at else "No expiry",
        "issued_on": fmt_date(card.issued_at), "member_since": fmt_date(card.issued_at, month_only=True),
    }
    for key, value in answers(card).items():
        if key in placed:
            values[f"field:{key}"] = str(value)[:120]
    live = tokens.live("programme_card", card)
    values["verify_url"] = tokens.short_url(live.token) if live else ""
    return values


def design(card):
    from apps.card_designs.resolution import resolve
    return resolve(card.makerspace_id, "id_programme", programme_id=card.programme_id)


def issuer(card):
    from apps.inventory import public_image_storage
    organization = card.programme.organization
    return {"kind": "organisation", "name": organization.name,
            "logo_url": public_image_storage.public_url(organization.logo_key) or None}


def logos(card):
    from apps.card_designs.images import read_public_image
    return {"space": read_public_image(card.makerspace.logo_key),
            "organisation": read_public_image(card.programme.organization.logo_key)}


def redact(card):
    from apps.card_designs.photos import remove
    if card.photo_object_key:
        remove(None, "programme_card", card)
    card.name, card.answers, card.email, card.email_digest = "", "", "", ""
    card.save(update_fields=["name", "answers", "email", "email_digest", "updated_at"])


def email(card):
    if card.user_id and card.user.email:
        return card.user.email
    return card.email


def register():
    from apps.card_designs.photos import photo_bytes
    from apps.card_designs.switches import programmes_on
    from .models import IdProgrammeCard
    register_kind(HolderKind(
        kind="programme_card", model=lambda: IdProgrammeCard, domain="id_programme", standing=standing,
        snapshot=snapshot, design=design, account_id=lambda card: card.user_id,
        switched_on=lambda card: programmes_on(card.makerspace),
        public_verify=lambda card: card.programme.public_verify, issuer=issuer, photo_bytes=photo_bytes, logos=logos,
        filename=lambda card: slugify(f"{card.id_number or card.pk}-{card.name}")[:80] or f"card-{card.pk}",
        label=lambda card: card.programme.name, redact=redact, email=email,
    ))
