"""Decision 221(f): managers of an event's organizer organizations in OTHER spaces hear a linked venue booking change."""
import pytest

from apps.accounts import rbac
from apps.events.linked_booking_notices import GRANT_SOURCE, notify_organizers
from apps.events.models import EventOrganizer
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.events.test_booking_decision_replacement import linked
from tests.machines.certification_helpers import _member

pytestmark = pytest.mark.django_db(transaction=True)


def organizer_member(event, slug, actions, *, active=True):
    other = Makerspace.objects.create(name=slug.title(), slug=slug)
    org = Organization.objects.create(name=slug.title(), slug=slug, is_active=active)
    OrganizationMakerspace.objects.create(organization=org, makerspace=other,
                                          relationship=OrganizationMakerspace.Relationship.AFFILIATE)
    EventOrganizer.objects.create(event=event, organization=org)
    user, _ = _member(other, f"{slug}-user")
    OrganizationMembership.objects.create(organization=org, user=user, granted_actions=actions)
    return user


def heard(event):
    return {row.recipient_id for row in NotificationEnvelope.objects.filter(
        source_kind=GRANT_SOURCE, source_id=str(event.pk))}


def test_an_organizer_organization_manager_in_another_space_hears_the_booking_moved():
    _maker, _staff, _member_row, event, _room, booking, _decision, _client = linked("o221-moved")
    manager = organizer_member(event, "o221-other", [rbac.Action.MANAGE_EVENTS])
    notify_organizers(booking, "moved")
    assert manager.pk in heard(event)


def test_an_organization_member_without_event_authority_hears_nothing():
    _maker, _staff, _member_row, event, _room, booking, _decision, _client = linked("o221-none")
    member = organizer_member(event, "o221-plain", [])
    notify_organizers(booking, "cancelled")
    assert member.pk not in heard(event)


def test_an_inactive_organizer_organization_hears_nothing():
    _maker, _staff, _member_row, event, _room, booking, _decision, _client = linked("o221-inactive")
    manager = organizer_member(event, "o221-dead", [rbac.Action.MANAGE_EVENTS], active=False)
    notify_organizers(booking, "moved")
    assert manager.pk not in heard(event)
