"""Public and collaborative lists batch attribution across occurrences and hosts."""

import pytest

from apps.events.models import Event, EventOrganizer, EventRegistration
from apps.events.organization_audience import AUDIENCE, FEATURE, audience_projection, audience_projections
from apps.events.serializers_collaborators import CollaborativeEventSerializer
from apps.events.serializers_event_details import EventAdminSerializer
from apps.events.serializers_organization_audience import (
    OrganizationAudienceFields, OrganizationAudienceListSerializer,
)
from apps.events.serializers_public import PublicEventSerializer
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.events.organization_audience_helpers import audience_fixture

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("serializer_class", [PublicEventSerializer, CollaborativeEventSerializer, EventAdminSerializer])
@pytest.mark.parametrize("audience", ["members", AUDIENCE])
@pytest.mark.parametrize("count", [1, 100])
@pytest.mark.parametrize("multiple_hosts", [False, True])
def test_list_projection_uses_three_queries_with_prefetched_organizers(
    serializer_class, audience, count, multiple_hosts, django_assert_num_queries,
):
    venue, orgs, sources, event, _ = audience_fixture()
    if audience == "members":
        # Ordinary member events still expose attribution when the audience feature is off.
        venue.enabled_features.remove(FEATURE)
        venue.save(update_fields=["enabled_features"])
    rows = Event.objects.bulk_create([Event(
        makerspace=sources[0] if multiple_hosts and index % 2 else venue,
        title=f"Occurrence {index}", starts_at=event.starts_at, ends_at=event.ends_at,
        registration_audience=audience, status="published", is_public=True,
    ) for index in range(count)])
    EventOrganizer.objects.bulk_create([EventOrganizer(
        event=row, organization=orgs[index % 2],
    ) for index, row in enumerate(rows)])
    events = list(Event.objects.filter(pk__in=[row.pk for row in rows]).select_related(
        "makerspace__payment_settings", "series", "category",
    ).prefetch_related("organizers__organization", "audience_organizations__organization").order_by("pk"))
    for row in events:
        row.confirmed_count = 0
        row.public_ticket_rows = []
        for status in EventRegistration.Status.values:
            setattr(row, f"{status}_count", 0)
    host_ids = {row.makerspace_id for row in events}
    context = {
        "omit_website": True,
        "event_authority": {(row._meta.label, row.pk): (False, []) for row in events},
        "active_host_waivers": {},
        "ticket_feature_flags": {pk: {"tickets": False, "promos": False, "membership": False}
                                 for pk in host_ids},
    }
    serializer = serializer_class(events, many=True, context=context)
    assert isinstance(serializer, OrganizationAudienceListSerializer)
    with django_assert_num_queries(3):
        data = serializer.data
    assert len(data) == count
    for index, (row, item) in enumerate(zip(events, data)):
        expected = sorted({orgs[index % 2].pk, orgs[0 if row.makerspace_id == sources[0].pk else 2].pk})
        assert item["participating_organizations"] == [
            {"id": org.pk, "name": org.name} for org in orgs if org.pk in expected
        ]
        names = ", ".join(org.name for org in orgs if org.pk in expected)
        assert item["audience_label"] == (f"Open to members of {names}" if audience == AUDIENCE else None)
        if serializer_class is EventAdminSerializer:
            enabled = FEATURE in row.makerspace.enabled_features
            assert (FEATURE in item["ticketing_features"]) is enabled
            assert item["offline_checkin_enabled"] is False


def test_unprefetched_projection_batches_organizers_in_one_query(django_assert_num_queries):
    venue, _, _, event, _ = audience_fixture()
    Event.objects.bulk_create([Event(
        makerspace=venue, title=f"Occurrence {index}", starts_at=event.starts_at, ends_at=event.ends_at,
        registration_audience=AUDIENCE,
    ) for index in range(20)])
    events = list(Event.objects.filter(makerspace=venue))
    # Hosts, owners, organizers, selected audience rows and organizations are each batched.
    with django_assert_num_queries(5):
        data = OrganizationAudienceFields(events, many=True).data
    assert len(data) == 21
    assert all(item["participating_organizations"] for item in data)


def test_projection_rechecks_active_organizations_and_owner_links_between_responses():
    venue, orgs, _, event, _ = audience_fixture()
    event = Event.objects.prefetch_related("organizers").get(pk=event.pk)
    assert len(OrganizationAudienceFields(event).data["participating_organizations"]) == 3
    Organization.objects.filter(pk=orgs[0].pk).update(is_active=False)
    OrganizationMakerspace.objects.filter(makerspace=venue, relationship="owner").delete()
    next_response = OrganizationAudienceFields(event).data
    assert next_response["participating_organizations"] == [{"id": orgs[1].pk, "name": "B"}]
    assert next_response["audience_label"] == "Open to members of B"


@pytest.mark.parametrize("state", ["archived", "inactive"])
def test_unusable_hosts_have_no_public_candidates_in_batched_or_single_projection(state):
    from django.utils import timezone
    venue, _, _, event, _ = audience_fixture()
    changes = {"archived": {"archived_at": timezone.now()},
               "inactive": {"lifecycle_state": "migrated_out"}}[state]
    Makerspace.objects.filter(pk=venue.pk).update(**changes)
    for projection in (audience_projection(event), audience_projections([event])[(event._meta.label, event.pk)]):
        assert projection["participating_organizations"] == []
        assert "none currently available" in projection["audience_label"]


def test_empty_projection_does_not_query(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert OrganizationAudienceFields([], many=True).data == []
