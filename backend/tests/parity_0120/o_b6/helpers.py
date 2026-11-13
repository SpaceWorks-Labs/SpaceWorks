"""O-B6 helpers: an organization workspace owned by a public organization."""
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace


def workspace(slug="club", *, kind="organization", public=True):
    space = Makerspace.objects.create(name=slug.title(), slug=slug, kind=kind)
    org = Organization.objects.create(name=f"{slug.title()} Org", slug=f"{slug}-org", public_profile_enabled=public)
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    return space, org
