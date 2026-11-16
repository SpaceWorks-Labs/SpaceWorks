"""The `staff_card` holder kind: a staff member's ID card over their staff-track membership (O-B4 part 2).

Standing: a revoked card, a revoked or missing staff membership, a disabled account or a restricted account
all read as revoked; otherwise valid. There is no expiry: the card is valid exactly while the staff access
lasts. The public check shows name, "Staff", the held roles and valid/revoked -- never contact details.
"""
from django.utils.translation import gettext
from django.utils.text import slugify

from .holders import HolderKind, register as register_kind
from .holders_member import fmt_date, owner_organization, _space_name


def _user(card):
    return card.membership.user if card.membership_id else None


def _access_ok(membership):
    user = membership.user
    return (membership.status == "active" and membership.track == "staff" and user.is_active
            and user.access_status == "active")


def standing(card):
    membership = card.membership
    if card.revoked_at is not None or membership is None or not _access_ok(membership):
        return "revoked"
    return "valid"


def snapshot(card):
    from . import tokens
    from .staff_card_roles import machine_scope_text, roles_text
    space = card.makerspace
    values = {"space": _space_name(space), "issued_on": fmt_date(card.issued_at)}
    organisation = owner_organization(space)
    values["organisation"] = organisation.name if organisation else ""
    membership = card.membership
    if membership is None:
        return values
    user = membership.user
    values["name"] = user.display_name or user.get_full_name() or user.username
    values["number"] = card.number_text or f"S-{card.card_number:04d}"
    roles = roles_text(membership)
    values["roles"] = values["role"] = roles
    values["machine_scope"] = machine_scope_text(membership)
    values["valid_until"] = gettext("While staff access lasts")
    values["member_since"] = fmt_date(membership.activated_at or membership.created_at, month_only=True)
    live = tokens.live("staff_card", card)
    values["verify_url"] = tokens.short_url(live.token) if live else ""
    from .unit_chain import values as unit_values
    values.update(unit_values(membership))
    return values


def design(card):
    from .resolution import resolve
    return resolve(card.makerspace_id, "staff_cards")


def switched_on(card):
    from .switches import staff_cards_on
    return staff_cards_on(card.makerspace)


def public_verify(card):
    from apps.makerspaces.models import MemberCardSettings
    return MemberCardSettings.objects.filter(makerspace_id=card.makerspace_id, public_verify=True).exists()


def issuer(card):
    from apps.inventory import public_image_storage
    space = card.makerspace
    from apps.makerspaces.space_kind import space_noun
    return {"kind": "space", "name": _space_name(space), "space_noun": space_noun(space),
            "logo_url": public_image_storage.public_url(space.logo_key) or None}


def photo_bytes(card):
    """The person's own member-card photo in this space, when they hold one (no second upload, no new copy)."""
    from apps.makerspaces.member_card_storage import photo_bytes as read
    from apps.makerspaces.models import MemberCard
    user = _user(card)
    if user is None:
        return None
    member_card = MemberCard.objects.filter(makerspace_id=card.makerspace_id, membership__user=user,
                                            revoked_at__isnull=True).exclude(photo_object_key="").first()
    return read(member_card) if member_card else None


def logos(card):
    from .images import read_public_image
    organisation = owner_organization(card.makerspace)
    return {"space": read_public_image(card.makerspace.logo_key),
            "organisation": read_public_image(organisation.logo_key) if organisation else None}


def filename(card):
    values = snapshot(card)
    return slugify(f"{values.get('number') or card.card_number}-{values.get('name', '')}")[:80] or f"staff-card-{card.pk}"


def register():
    from .models_staff_cards import StaffCard
    register_kind(HolderKind(
        kind="staff_card", model=lambda: StaffCard, domain="staff_cards", standing=standing, snapshot=snapshot,
        design=design, account_id=lambda card: card.membership.user_id if card.membership_id else None,
        switched_on=switched_on, public_verify=public_verify, issuer=issuer, photo_bytes=photo_bytes,
        logos=logos, filename=filename, label=lambda card: snapshot(card).get("roles", ""),
        email=lambda card: card.membership.user.email if card.membership_id else "",
    ))
