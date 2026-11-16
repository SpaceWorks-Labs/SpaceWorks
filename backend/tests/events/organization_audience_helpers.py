from apps.events.models import EventOrganizer
from apps.events.organization_audience import AUDIENCE, FEATURE
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event


def audience_fixture(**values):
    venue = event_space("org-venue")
    venue.enabled_features += [FEATURE]
    venue.save(update_fields=["enabled_features"])
    organizations = [Organization.objects.create(name=name, slug=name.lower()) for name in ("A", "B", "C")]
    sources = [event_space("org-a-source"), event_space("org-b-source"), venue]
    for org, space in zip(organizations, sources):
        OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    event = open_event(venue, AUDIENCE, **values)
    for org in organizations[:2]:
        EventOrganizer.objects.create(event=event, organization=org)
    manager = make_staff(venue)
    return venue, organizations, sources, event, manager


def direct(org, name="org-participant", **values):
    user = account(name)
    OrganizationMembership.objects.create(organization=org, user=user, granted_actions=[], **values)
    return user


def local(space, name="local-participant", **values):
    user = account(name)
    # The model's legacy default is Space Manager; this participant has no actions.
    values.setdefault("role", MakerspaceMembership.Role.CUSTOM)
    values.setdefault("assigned_role", space.roles.get(slug="member"))
    MakerspaceMembership.objects.create(makerspace=space, user=user, status="active", **values)
    return user
