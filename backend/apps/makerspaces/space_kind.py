"""Decision 295: a space is a makerspace or an organization workspace.

The kind changes defaults and wording only. Every module and feature stays switchable
afterwards (decision 254), so nothing here is a gate: an organization workspace may turn
Inventory on later, and a makerspace may run events and bookings without lending.
"""
from django.utils.translation import gettext

MAKERSPACE = "makerspace"
ORGANIZATION = "organization"
KINDS = (MAKERSPACE, ORGANIZATION)
# Setup areas (decision 254) an organization workspace starts with; Inventory and
# Machines are off. Memberships carries the member and ID cards.
ORGANIZATION_AREAS = ("events", "membership", "bookings")


def kind_of(space) -> str:
    return ORGANIZATION if getattr(space, "kind", MAKERSPACE) == ORGANIZATION else MAKERSPACE


def is_organization(space) -> bool:
    return kind_of(space) == ORGANIZATION


def space_noun(space) -> str:
    """The wording key the frontend translates: ``makerspace`` or ``organization``."""
    return kind_of(space)


def noun_label(space) -> str:
    """The translated noun for server-built sentences (use as a ``{noun}`` placeholder)."""
    return gettext("organization") if is_organization(space) else gettext("makerspace")


def kind_payload(space) -> dict:
    return {"kind": kind_of(space), "space_noun": space_noun(space)}


def bootstrap_kind_payload(space) -> dict:
    """Emitted for an organization workspace only (absent = makerspace): the kind, the
    wording noun and the organization page its /m/ URL redirects to (null while that page
    is not public)."""
    if not is_organization(space):
        return {}
    from apps.makerspaces.public_page_access import _public_home_organization
    home = _public_home_organization(space)
    return {**kind_payload(space), "organization_page_slug": home.slug if home else None}


def apply_kind_defaults(actor, space):
    """Give a freshly created organization workspace its default areas; makerspaces keep the
    registry defaults. Runs inside the creation transaction."""
    if not is_organization(space):
        return space
    from apps.makerspaces.setup_area_application import apply_areas
    return apply_areas(actor, space, {"areas": list(ORGANIZATION_AREAS)})
