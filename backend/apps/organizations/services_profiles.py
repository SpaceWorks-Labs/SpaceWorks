from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.organizations import governance
from apps.organizations.access import lock_governance_membership
from apps.organizations.models import Organization


PUBLIC_PROFILE_FIELDS = frozenset(
    {"name", "slug", "description", "website", "public_profile_enabled", "is_discoverable"}
)


@transaction.atomic
def update_profile(organization, *, actor, **changes):
    from apps.makerspaces.public_page_authority import reject_platform
    reject_platform(actor)
    unknown = set(changes) - PUBLIC_PROFILE_FIELDS
    if unknown:
        raise ValidationError({field: "This field cannot be edited here." for field in unknown})

    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    lock_governance_membership(
        actor,
        locked,
        governance.MANAGE_ORGANIZATION_PROFILE,
    )
    from .models_public_pages import OrganizationPublicPage
    page = OrganizationPublicPage.objects.select_for_update().filter(organization=locked).first()
    if page and changes.get("public_profile_enabled") is True and not page.published_revision_id:
        raise ValidationError({"public_profile_enabled": "Publish the current saved page draft to enable its public profile."})
    if page and changes.get("public_profile_enabled") is False:
        page.published_revision = None
        page.version += 1
        page.save(update_fields=["published_revision", "version"])
    changed_fields = []
    for field, value in changes.items():
        if getattr(locked, field) != value:
            setattr(locked, field, value)
            changed_fields.append(field)
    if changed_fields:
        locked.save(update_fields=[*changed_fields, "updated_at"])
        audit.record(
            actor,
            "organization.profile_updated",
            target=locked,
            meta={"fields": sorted(changed_fields), "slug": locked.slug},
        )
    return locked
