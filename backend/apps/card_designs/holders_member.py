"""The `member_card` holder kind: a makerspace member's card over their membership.

Standing (SPEC §7): revoked card, revoked membership or no membership -> revoked;
otherwise valid while a term is current (grace counts as valid, Q4) and expired once
the last term has ended. A membership that has never had a term is open-ended and
valid. A lapse never revokes (X26): verify derives Expired live from the terms.
"""
from django.utils import timezone
from django.utils.text import slugify

from .holders import HolderKind, register as register_kind


def fmt_date(value, *, month_only=False):
    if not value:
        return ""
    value = value.date() if hasattr(value, "date") and callable(value.date) else value
    return value.strftime("%b %Y") if month_only else f"{value.day} {value:%b %Y}"


def live_terms(membership, now=None):
    from apps.makerspaces.membership_renewals import grace_end
    from apps.makerspaces.models_membership_terms import MembershipTerm
    now = now or timezone.now()
    rows = MembershipTerm.objects.filter(membership=membership, status="active", starts_at__lte=now).select_related(
        "plan", "membership__makerspace")
    return [term for term in rows if grace_end(term) > now]


def term_state(membership):
    """('open'|'current'|'ended', live term or None)."""
    from apps.makerspaces.models_membership_terms import MembershipTerm
    current = live_terms(membership)
    if current:
        return "current", max(current, key=lambda term: term.ends_at)
    if not MembershipTerm.objects.filter(membership=membership).exists():
        return "open", None
    return "ended", None


def standing(card):
    membership = card.membership
    if card.revoked_at is not None or membership is None or membership.status != "active":
        return "revoked"
    state, _term = term_state(membership)
    return "expired" if state == "ended" else "valid"


def _space_name(space):
    return (space.branding_config or {}).get("display_name") or space.name


def owner_organization(space):
    from apps.organizations.models import OrganizationMakerspace
    link = OrganizationMakerspace.objects.filter(makerspace=space, relationship="owner").select_related(
        "organization").first()
    return link.organization if link else None


def snapshot(card):
    from apps.makerspaces.membership_number import display_number
    from apps.makerspaces.membership_titles import primary_title
    membership = card.membership
    space = card.makerspace
    values = {"space": _space_name(space), "issued_on": fmt_date(card.issued_at)}
    organisation = owner_organization(space)
    values["organisation"] = organisation.name if organisation else ""
    if membership is None:
        return {**values, "name": card.printed_name}
    user = membership.user
    values["name"] = card.printed_name or user.display_name or user.get_full_name() or user.username
    values["number"] = display_number(membership) if membership.member_number else str(card.card_number)
    state, term = term_state(membership)
    values["plan"] = term.plan.name if term else ""
    values["valid_until"] = fmt_date(term.ends_at) if term else ("No end date" if state == "open" else "Expired")
    values["member_since"] = fmt_date(membership.activated_at, month_only=True)
    title = primary_title(membership)
    role = membership.assigned_role.name if membership.assigned_role_id else ""
    values["title"] = title.name if title else ""
    values["role"] = values["title"] or role
    from . import tokens
    live = tokens.live("member_card", card)
    values["verify_url"] = tokens.short_url(live.token) if live else ""
    from apps.machines.certifications import live_certification_names
    values["certifications"] = ", ".join(live_certification_names(membership))
    return values


def design(card):
    from apps.makerspaces.membership_titles import primary_title
    from .resolution import resolve
    membership = card.membership
    title = primary_title(membership) if membership else None
    _state, term = term_state(membership) if membership else (None, None)
    return resolve(card.makerspace_id, "member_cards", title_id=title.pk if title else None,
                   plan_id=term.plan_id if term else None)


def switched_on(card):
    from apps.makerspaces.platform import module_enabled
    return module_enabled(card.makerspace, "membership")


def public_verify(card):
    from apps.makerspaces.models import MemberCardSettings
    return MemberCardSettings.objects.filter(makerspace_id=card.makerspace_id, public_verify=True).exists()


def issuer(card):
    from apps.inventory import public_image_storage
    space = card.makerspace
    return {"kind": "space", "name": _space_name(space),
            "logo_url": public_image_storage.public_url(space.logo_key) or None}


def photo_bytes(card):
    from apps.makerspaces.member_card_storage import photo_bytes as read
    return read(card)


def logos(card):
    from .images import read_public_image
    organisation = owner_organization(card.makerspace)
    return {"space": read_public_image(card.makerspace.logo_key),
            "organisation": read_public_image(organisation.logo_key) if organisation else None}


def filename(card):
    values = snapshot(card)
    return slugify(f"{values.get('number') or card.card_number}-{values.get('name', '')}")[:80] or f"card-{card.pk}"


def desk_payload(card):
    from apps.makerspaces.member_card_services import active_qr
    qr = active_qr(card)
    return qr.payload if qr else None


def redact(card):
    from apps.makerspaces.member_card_services import redact as redact_card
    redact_card(card)


def register():
    from apps.makerspaces.models import MemberCard
    register_kind(HolderKind(
        kind="member_card", model=lambda: MemberCard, domain="member_cards", standing=standing,
        snapshot=snapshot, design=design,
        account_id=lambda card: card.membership.user_id if card.membership_id else None,
        switched_on=switched_on, public_verify=public_verify, issuer=issuer, photo_bytes=photo_bytes,
        logos=logos, filename=filename, desk_payload=desk_payload,
        label=lambda card: snapshot(card).get("plan", ""), redact=redact,
        email=lambda card: card.membership.user.email if card.membership_id else "",
    ))
