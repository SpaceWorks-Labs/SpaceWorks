"""The pre-filled /control/ "Add makerspace" link for an accepted request.

Nothing is provisioned here: the link only fills the existing add form. "Join" fills the
inviting organization as owner; "own" fills a new organization name. When the applicant
chose Join but that organization is gone or inactive, BOTH owner fields are left empty
so the add form's exactly-one rule makes the superadmin choose -- the request is never
silently switched to "own".
"""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.text import slugify

from apps.hosting_requests.models import HostingRequest

JOIN = HostingRequest.OrganizationChoice.JOIN


def join_organization(row):
    organization = row.inviter_organization
    if row.organization_choice != JOIN or organization is None or not organization.is_active:
        return None
    return organization


def add_url(row):
    query = {
        "name": row.space_name,
        "slug": row.proposed_slug or slugify(row.space_name)[:50],
        "location": row.location,
        "hosting_request": row.pk,
        "kind": row.requested_kind,
    }
    organization = join_organization(row)
    if organization is not None:
        query["owner_organization"] = organization.pk
    elif row.organization_choice != JOIN:
        query["new_organization_name"] = row.new_organization_name or row.space_name
    return reverse("admin:makerspaces_makerspace_add") + "?" + urlencode(query)


def owner_choice_summary(row):
    if row.organization_choice != JOIN:
        name = row.new_organization_name or row.space_name
        return f"Applicant chose to create their own organization ({name})."
    organization = join_organization(row)
    if organization is not None:
        return f"Applicant chose to join {organization.name}; it is pre-filled as the owner."
    named = row.inviter_organization.name if row.inviter_organization else "the inviting organization"
    return (
        f"Applicant chose to join {named}, which is no longer active — choose an owner "
        "on the add form."
    )
