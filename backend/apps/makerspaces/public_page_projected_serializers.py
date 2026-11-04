"""Public payloads are live projections, distinct from editor input documents."""

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field, extend_schema_serializer
from rest_framework import serializers as s
from .public_page_sections import About, Links, Testimonials, Titled
from .public_page_contract import PALETTES


class PublicGalleryItem(s.Serializer):
    url = s.CharField(allow_null=True)
    alt = s.CharField()
    caption = s.CharField(allow_blank=True)


class PublicGallery(Titled):
    items = PublicGalleryItem(many=True)


class ExplicitTeamEntry(s.Serializer):
    id = s.UUIDField()
    kind = s.ChoiceField(choices=("explicit",))
    display_name = s.CharField()
    role = s.CharField(allow_blank=True)
    url = s.CharField(required=False, allow_blank=True)


class MemberTeamEntry(ExplicitTeamEntry):
    kind = s.ChoiceField(choices=("member",))
    handle = s.CharField()
    avatar_url = s.CharField(allow_null=True)


@extend_schema_field(PolymorphicProxySerializer(component_name="PublicTeamEntry",
    serializers={"explicit": ExplicitTeamEntry, "member": MemberTeamEntry}, resource_type_field_name="kind", many=True))
class PublicTeamEntries(s.Field):
    def to_representation(self, value):
        return [(MemberTeamEntry if row["kind"] == "member" else ExplicitTeamEntry)(row).data for row in value]


class PublicTeam(Titled):
    entries = PublicTeamEntries()


class EventCard(s.Serializer):
    title = s.CharField()
    starts_at = s.DateTimeField()
    ends_at = s.DateTimeField()
    event_url = s.CharField()


class PublicUpcoming(Titled):
    count = s.IntegerField()
    results = EventCard(many=True)
    collection_url = s.CharField()


class EventCollection(s.Serializer):
    count = s.IntegerField()
    results = EventCard(many=True)
    collection_url = s.CharField()


class ArchiveHost(s.Serializer):
    name = s.CharField()
    canonical_url = s.CharField()


class ArchiveCard(EventCard):
    kind = s.ChoiceField(choices=("archive",))
    description = s.CharField(allow_blank=True)
    timezone = s.CharField()
    event_url = s.CharField(allow_null=True)
    host = ArchiveHost()


class ArchiveCollection(EventCollection):
    results = ArchiveCard(many=True)


class PublicOrganizationEvents(Titled):
    upcoming = EventCollection()
    past = ArchiveCollection()


class SpaceCard(ArchiveHost):
    slug = s.CharField()
    logo_url = s.CharField(allow_null=True)


class PublicLinkedSpaces(Titled):
    count = s.IntegerField()
    results = SpaceCard(many=True)
    collection_url = s.CharField()


class PublicMetrics(s.Serializer):
    public_exact_count_subset_units = s.IntegerField(required=False)
    published_event_count = s.IntegerField(required=False)
    public_member_count = s.IntegerField(required=False)


@extend_schema_serializer(component_name="PublicPageStats")
class PublicStats(Titled):
    metrics = PublicMetrics()


class PublicLocation(Titled):
    enabled_publicly = s.BooleanField()
    source = s.ChoiceField(choices=("makerspace_public", "entered"), required=False)
    address = s.CharField(allow_blank=True, required=False)
    map_url = s.CharField(allow_blank=True, required=False)
    latitude = s.FloatField(allow_null=True, required=False)
    longitude = s.FloatField(allow_null=True, required=False)
    directions = s.CharField(allow_blank=True, required=False)


class FunctionalLink(s.Serializer):
    family = s.ChoiceField(choices=("inventory", "events", "bookings", "machines", "membership"))
    url = s.CharField()


class PublicFunctional(s.Serializer):
    links = FunctionalLink(many=True)


class PublicPlanCard(s.Serializer):
    id = s.IntegerField()
    slug = s.CharField(allow_blank=True)
    name = s.CharField()
    description = s.CharField(allow_blank=True)
    plan_type = s.CharField()
    interval = s.CharField()
    custom_days = s.IntegerField(allow_null=True)
    fixed_end_date = s.DateField(allow_null=True)
    amount = s.DecimalField(max_digits=12, decimal_places=2)
    renewal_price = s.DecimalField(max_digits=12, decimal_places=2)
    currency = s.CharField()
    joining_fee = s.CharField(allow_null=True)
    join_mode = s.CharField()


class PublicMembershipPlans(Titled):
    count = s.IntegerField()
    results = PublicPlanCard(many=True)
    collection_url = s.CharField()


PUBLIC_PAYLOADS = {"about": About, "gallery": PublicGallery, "team": PublicTeam,
    "testimonials": Testimonials, "links": Links, "upcoming_events": PublicUpcoming,
    "organization_events": PublicOrganizationEvents, "linked_makerspaces": PublicLinkedSpaces,
    "stats": PublicStats, "location": PublicLocation, "functional_content": PublicFunctional,
    "membership_plans": PublicMembershipPlans}


class ProjectedSection(s.Serializer):
    id = s.UUIDField()
    type = s.ChoiceField(choices=tuple(PUBLIC_PAYLOADS))
    enabled = s.BooleanField()


PROJECTED_TYPES = {key: type(f"Public{key.title().replace('_', '')}Section", (ProjectedSection,), {
    "type": s.ChoiceField(choices=(key,)), "payload": serializer(),
}) for key, serializer in PUBLIC_PAYLOADS.items()}


@extend_schema_field(PolymorphicProxySerializer(component_name="ProjectedPublicPageSection",
    serializers=PROJECTED_TYPES, resource_type_field_name="type", many=True))
class ProjectedSections(s.Field):
    def to_representation(self, value):
        return [PROJECTED_TYPES[row["type"]](row).data for row in value]


class ProjectedDocument(s.Serializer):
    schema_version = s.IntegerField(min_value=1, max_value=1)
    cover_mode = s.ChoiceField(choices=("inherit", "asset", "none"))
    cover_asset_id = s.IntegerField(allow_null=True)
    accent_choice = s.ChoiceField(choices=("inherit", *PALETTES), allow_null=True)
    sections = ProjectedSections()
