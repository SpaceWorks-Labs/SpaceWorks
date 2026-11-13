"""Opt-in public organization directory (PP1).

Listed only when ALL gates hold: the deployment switch `ORGANIZATION_PUBLIC_DIRECTORY_ENABLED`,
the organization's own `is_discoverable` and `public_profile_enabled`, and an approved,
active organization. A published builder page that is unpublished again hides it too,
exactly as the single-organization page does.
"""
from django.conf import settings
from django.db.models import Q

from apps.organizations.models import Organization


def directory_enabled() -> bool:
    return bool(getattr(settings, "ORGANIZATION_PUBLIC_DIRECTORY_ENABLED", False))


def directory_organizations(search=""):
    if not directory_enabled():
        return Organization.objects.none()
    rows = Organization.objects.filter(
        is_active=True, review_status="approved", is_discoverable=True, public_profile_enabled=True,
    ).filter(Q(public_page__isnull=True) | Q(public_page__published_revision__isnull=False))
    search = (search or "").strip()[:100]
    if search:
        rows = rows.filter(name__icontains=search)
    return rows.select_related("public_page", "public_handle").order_by("name", "id")


def directory_card(organization):
    from apps.inventory.public_image_storage import public_url
    from apps.makerspaces.public_page_access import canonical_url
    claim = getattr(organization, "public_handle", None)
    page = getattr(organization, "public_page", None)
    handle = claim.handle if claim and page and page.published_revision_id else None
    return {"name": organization.name, "slug": organization.slug,
            "description": (organization.description or "")[:200],
            "logo_url": public_url(organization.logo_key) or None,
            "canonical_url": canonical_url("organization", organization, handle)}
