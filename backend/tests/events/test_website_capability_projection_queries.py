"""Staff website flags share the per-response, per-host capability projection."""

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.events.serializers_event_details import EventAdminSerializer
from apps.makerspaces.models import Makerspace
from tests.events.organization_audience_helpers import audience_fixture

pytestmark = pytest.mark.django_db


class StaffCapabilitySerializer(EventAdminSerializer):
    # Exercise the real list serializer and capability methods, isolating their
    # query budget from unrelated staff fields (reports, broadcasts, counts).
    class Meta(EventAdminSerializer.Meta):
        fields = ("id", "ticketing_features")
        read_only_fields = fields


def forbid_per_row_feature_lookup(*args, **kwargs):
    pytest.fail("Staff list capabilities must use the batched host flags")


@pytest.mark.parametrize("count", [1, 24, 200])
@pytest.mark.parametrize("features,expected", [
    ([], []),
    (["events.website"], ["events.website"]),
    (["events.website", "events.embed"], ["events.website", "events.embed"]),
    # Stored embed enablement cannot bypass its website prerequisite.
    (["events.embed"], []),
])
def test_staff_website_flags_have_constant_query_cost(
    count, features, expected, monkeypatch, django_assert_num_queries,
):
    venue, _, sources, template, _ = audience_fixture()
    # Different host settings must not bleed across events in the same response.
    Makerspace.objects.filter(pk=venue.pk).update(enabled_features=features)
    Makerspace.objects.filter(pk=sources[0].pk).update(enabled_features=[])
    rows = Event.objects.bulk_create([Event(
        makerspace_id=sources[0].pk if index % 2 else venue.pk,
        title=f"Website occurrence {index}",
        starts_at=template.starts_at, ends_at=template.ends_at,
    ) for index in range(count)])
    events = list(Event.objects.filter(pk__in=[row.pk for row in rows]).prefetch_related(
        "organizers",
    ).order_by("pk"))
    monkeypatch.setattr(
        "apps.events.serializers_event_details.feature_enabled", forbid_per_row_feature_lookup,
    )
    # One query each for usable hosts, owner links and organization attribution,
    # regardless of page size or whether either website flag is enabled.
    with django_assert_num_queries(3):
        data = StaffCapabilitySerializer(events, many=True).data
    assert len(data) == count
    for event, item in zip(events, data):
        assert item["ticketing_features"] == (expected if event.makerspace_id == venue.pk else [])


@pytest.mark.parametrize("state", ["archived", "inactive", "events_disabled"])
def test_staff_website_flags_refuse_unusable_hosts_and_disabled_module(state, monkeypatch):
    venue, _, _, event, _ = audience_fixture()
    changes = {
        "archived": {"archived_at": timezone.now()},
        "inactive": {"lifecycle_state": "migrated_out"},
        "events_disabled": {"enabled_modules": []},
    }[state]
    Makerspace.objects.filter(pk=venue.pk).update(
        enabled_features=["events.website", "events.embed"], **changes,
    )
    monkeypatch.setattr(
        "apps.events.serializers_event_details.feature_enabled", forbid_per_row_feature_lookup,
    )
    assert StaffCapabilitySerializer([event], many=True).data[0]["ticketing_features"] == []
