"""Project the home space's public membership plans onto the organization page (PP3).

The home space is the organization's lowest-id OWNER-linked space that is servable and
public. Its plans appear only while `membership` and `membership.public_plans` are on for
that space (`plan_cards` enforces both); otherwise the page carries `plans: null`. No
organization-level plan exists, and the member card is the home space's card.
"""
from apps.organizations.models import OrganizationMakerspace
from apps.organizations.public_catalog import linked_spaces_for


def home_space(organization):
    owned = OrganizationMakerspace.objects.filter(
        organization=organization, relationship="owner").values("makerspace_id")
    return linked_spaces_for(organization).filter(pk__in=owned).order_by("pk").first()


def home_space_plans(organization):
    space = home_space(organization)
    if space is None:
        return None
    from apps.makerspaces.public_page_plans import plan_cards
    return plan_cards(space, "")
