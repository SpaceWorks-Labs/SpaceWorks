"""Speaker identity and event-history shapes. No email, phone or bearer ever leaves here."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import EventCategory, EventSpeaker, EventTicketType


class SpeakerAccountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class EventSpeakerSerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(read_only=True)
    user = serializers.SerializerMethodField()
    section_slug = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=("linked", "invited", "removed"), read_only=True)

    class Meta:
        model = EventSpeaker
        fields = ("id", "event_id", "display_name", "user", "section_slug", "status", "linked_via",
                  "grants_check_in", "claim_expires_at", "claimed_at", "created_at", "removed_at")
        read_only_fields = fields

    @extend_schema_field(SpeakerAccountSerializer(allow_null=True))
    def get_user(self, obj):
        from .speaker_identity import display_name
        return {"id": obj.user_id, "display_name": display_name(obj.user)} if obj.user_id else None

    def get_section_slug(self, obj) -> str | None:
        return obj.section.slug if obj.section_id else None


class EventSpeakerListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = EventSpeakerSerializer(many=True)


class SpeakerAssignInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    display_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    section_slug = serializers.SlugField(max_length=80, required=False, allow_blank=True, default="")
    grant_check_in = serializers.BooleanField(required=False, default=False)


class SpeakerInviteInputSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=200)
    section_slug = serializers.SlugField(max_length=80, required=False, allow_blank=True, default="")
    grant_check_in = serializers.BooleanField(required=False, default=False)


class SpeakerInviteResponseSerializer(serializers.Serializer):
    speaker = EventSpeakerSerializer()
    claim_url = serializers.CharField(help_text="Shown once; the bearer travels only in the URL fragment.")


class SpeakerCandidateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()
    username = serializers.CharField()
    relation = serializers.ChoiceField(choices=("member", "staff", "registrant"))


class SpeakerCandidateListSerializer(serializers.Serializer):
    results = SpeakerCandidateSerializer(many=True)


class SpeakerClaimInputSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class SpeakerClaimEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class SpeakerClaimResponseSerializer(serializers.Serializer):
    speaker_id = serializers.IntegerField()
    display_name = serializers.CharField()
    event = SpeakerClaimEventSerializer()


class HistoryEventSerializer(SpeakerClaimEventSerializer):
    location = serializers.CharField()
    status = serializers.CharField()


class HistoryCountsSerializer(serializers.Serializer):
    registered = serializers.IntegerField()
    attended = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    speaking = serializers.IntegerField()


class HistoryRegistrationSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    status = serializers.CharField()
    event = HistoryEventSerializer()


class HistorySpeakingSerializer(serializers.Serializer):
    speaker_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=("speaker",))
    occurred_at = serializers.DateTimeField()
    event = HistoryEventSerializer()


class EventHistorySerializer(serializers.Serializer):
    counts = HistoryCountsSerializer()
    registrations = HistoryRegistrationSerializer(many=True)
    speaking = HistorySpeakingSerializer(many=True)


class TicketPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTicketType
        fields = ("name", "amount", "audience", "capacity", "sales_start_at", "sales_end_at", "is_active",
                  # Release 2 L6 (G29): order fields.
                  "tier_group", "tier_rank", "pricing_mode", "min_amount", "seats_per_ticket", "is_hidden", "min_quantity", "per_order_limit")
        extra_kwargs = {field: {"required": False} for field in fields}


class CategoryPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ("name", "slug")
        extra_kwargs = {"name": {"required": False}, "slug": {"required": False}}
