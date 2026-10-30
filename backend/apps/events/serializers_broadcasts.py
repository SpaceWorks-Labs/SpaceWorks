from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import EventRegistration
from .models_broadcasts import EventBroadcast
from .programme.broadcast_content import DESIGNS, unpack, validate_ctas


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"code": "unknown_fields", "detail": "Use only the documented fields."})
        return super().to_internal_value(data)


class BroadcastCtaSerializer(ClosedSerializer):
    kind = serializers.ChoiceField(choices=["https", "navigation"])
    label = serializers.CharField(max_length=80)
    url = serializers.URLField(required=False, max_length=2048)
    target = serializers.ChoiceField(choices=["event", "ticket"], required=False)

    def validate(self, attrs):
        return validate_ctas([attrs])[0]


class EventBroadcastInputSerializer(ClosedSerializer):
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000)
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=EventRegistration.Status.choices),
                                    min_length=1, max_length=6, default=["registered", "attended"])
    attendance = serializers.ChoiceField(choices=["any", "attended", "not_attended"], default="any")
    render_schema_version = serializers.ChoiceField(choices=[1, 2], default=1)
    design = serializers.ChoiceField(choices=DESIGNS, default="classic")
    ctas = BroadcastCtaSerializer(many=True, max_length=3, default=list)


class EventBroadcastSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()
    ctas = serializers.SerializerMethodField()

    def get_body(self, obj) -> str:
        return unpack(obj)["markdown"]

    @extend_schema_field(BroadcastCtaSerializer(many=True))
    def get_ctas(self, obj) -> list[dict]:
        return unpack(obj)["ctas"]

    class Meta:
        model = EventBroadcast
        fields = ("id", "event", "subject", "body", "statuses", "attendance", "status", "created_at",
                  "queued_at", "completed_at", "version", "render_schema_version", "design", "ctas", "available_at",
                  "undo_hold")
        read_only_fields = fields


class EventBroadcastListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = EventBroadcastSerializer(many=True)


class BulkInviteInputSerializer(serializers.Serializer):
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=200)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    send_email = serializers.BooleanField(default=True)


class BulkInviteResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()


class BroadcastCommandSerializer(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)


class BroadcastDraftContentSerializer(ClosedSerializer):
    subject = serializers.CharField(max_length=200, allow_blank=True)
    body = serializers.CharField(max_length=10000, allow_blank=True)
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=EventRegistration.Status.choices),
                                    min_length=1, max_length=6)
    attendance = serializers.ChoiceField(choices=["any", "attended", "not_attended"])
    design = serializers.ChoiceField(choices=DESIGNS)
    ctas = BroadcastCtaSerializer(many=True, max_length=3, default=list)


class BroadcastDraftSerializer(BroadcastCommandSerializer):
    draft = BroadcastDraftContentSerializer()


class BroadcastTestSerializer(BroadcastCommandSerializer):
    preview_id = serializers.IntegerField(min_value=1)


class BroadcastSendSerializer(BroadcastTestSerializer):
    revision = serializers.RegexField(r"^[a-f0-9]{64}$")
    recipient_count = serializers.IntegerField(min_value=0)
    confirm = serializers.BooleanField()


class BroadcastScheduleSerializer(BroadcastSendSerializer):
    available_at = serializers.DateTimeField()


class BroadcastTalliesSerializer(serializers.Serializer):
    campaign_id = serializers.IntegerField()
    status = serializers.CharField()
    total = serializers.IntegerField(min_value=0)
    delivered = serializers.IntegerField(min_value=0)
    waiting = serializers.IntegerField(min_value=0)
    failed = serializers.IntegerField(min_value=0)
    skipped = serializers.IntegerField(min_value=0)


class BroadcastTemplateSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    subject = serializers.CharField()
    body = serializers.CharField()
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=EventRegistration.Status.choices))
    attendance = serializers.ChoiceField(choices=["any", "attended", "not_attended"])
    design = serializers.ChoiceField(choices=DESIGNS)


class BroadcastPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["ready", "scheduled", "queued", "sending", "sent", "cancelled", "failed"])
    allowed_actions = serializers.ListField(child=serializers.ChoiceField(choices=["test", "schedule"]))
    preview_id = serializers.IntegerField()
    revision = serializers.CharField()
    recipient_count = serializers.IntegerField()
    subject = serializers.CharField()
    text = serializers.CharField()
    desktop_html = serializers.CharField()
    mobile_html = serializers.CharField()


class BroadcastTestResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    allowed_actions = serializers.ListField(child=serializers.CharField(), max_length=0)
    state = serializers.ChoiceField(choices=["queued", "skipped", "failed"])
    recipient = serializers.ChoiceField(choices=["self"])
