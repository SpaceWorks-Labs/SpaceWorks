from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, dict) else set()
        if unknown:
            raise serializers.ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class CommandSerializer(StrictSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class WindowSerializer(StrictSerializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": "End must follow start."})
        return {k: v.isoformat() for k, v in attrs.items()}


class RoleInputSerializer(CommandSerializer):
    form = serializers.DictField()
    answers = serializers.DictField()
    derivations = serializers.DictField(default=dict)
    save_choices = serializers.DictField(child=serializers.BooleanField(), default=dict)
    saved_detail_versions = serializers.DictField(child=serializers.IntegerField(min_value=0), default=dict)
    coc = serializers.DictField(required=False)
    optional_consents = serializers.DictField(required=False)
    event_date_revision = serializers.IntegerField(min_value=1)
    availability = WindowSerializer(many=True, max_length=50, required=False)
    skills = serializers.ListField(child=serializers.SlugField(max_length=40), max_length=50, required=False)
    host_waiver_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    host_waiver_version = serializers.CharField(max_length=64, required=False)
    host_waiver_accepted = serializers.BooleanField(required=False)


class ReasonCommandSerializer(CommandSerializer):
    reason_code = serializers.ChoiceField(choices=["availability_changed", "plans_changed",
        "solved_by_team", "organizer_revoked"], required=False)


class DateReviewSerializer(CommandSerializer):
    event_date_revision = serializers.IntegerField(min_value=1)
    reviewed_as_of_date = serializers.DateField()


class ShiftApplySerializer(CommandSerializer):
    role_assignment_id = serializers.IntegerField(min_value=1)


class HoursAdjustSerializer(CommandSerializer):
    minutes = serializers.IntegerField(min_value=0, max_value=1440)
    reason = serializers.CharField(max_length=2000)


class AggregateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField(required=False)
    allowed_actions = serializers.ListField(child=serializers.CharField())


class RoleSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["draft", "proposed", "applied", "approved", "declined", "withdrawn", "revoked", "completed"])
    role = serializers.CharField()
    posting_id = serializers.IntegerField(allow_null=True)
    answers = serializers.JSONField(required=False)
    form = serializers.JSONField(required=False)
    answer_review = serializers.JSONField(required=False)
    submitted_at = serializers.DateTimeField(allow_null=True)
    decision = serializers.CharField(allow_null=True)
    grant = serializers.IntegerField(allow_null=True)
    save_intent = serializers.JSONField(allow_null=True)
    entitlement_active = serializers.BooleanField(required=False)
    imported_inert = serializers.BooleanField(required=False)


class PostingSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["draft", "open", "closed"])
    role = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(required=False)
    form = serializers.JSONField(required=False)
    coc = serializers.JSONField(required=False)
    host_waiver = serializers.JSONField(required=False, allow_null=True)
    application = serializers.JSONField(allow_null=True, required=False)


class AdminPostingSerializer(PostingSerializer):
    briefing = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())
    visibility = serializers.CharField()
    approval_required = serializers.BooleanField()
    opens_at = serializers.DateTimeField()
    closes_at = serializers.DateTimeField()
    requirements = serializers.JSONField()
    permission_preset = serializers.ListField(child=serializers.CharField())
    form_schema = serializers.JSONField()


class ShiftSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["open", "closed"])
    posting_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["volunteer", "office_hours"])
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    task = serializers.CharField()
    zone = serializers.CharField()
    capacity = serializers.IntegerField()
    available = serializers.IntegerField(allow_null=True)
    mentor_card = serializers.JSONField(allow_null=True)
    signup = serializers.JSONField(allow_null=True)


class SignupSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["applied", "waitlisted", "approved", "withdrawn", "declined"])
    shift_id = serializers.IntegerField()
    attendance = serializers.CharField(allow_null=True)
    verified_minutes = serializers.IntegerField(allow_null=True)
    member_id = serializers.IntegerField(required=False)
    assignment_id = serializers.IntegerField(required=False)


class AdminShiftSerializer(ShiftSerializer):
    signups = SignupSerializer(many=True)
    signup_deadline = serializers.DateTimeField()
    mentor_assignment_id = serializers.IntegerField(allow_null=True)
    grace_minutes = serializers.IntegerField()
    waitlist_enabled = serializers.BooleanField()
    approval_required = serializers.BooleanField()
    requirements = serializers.JSONField()
    permission_preset = serializers.ListField(child=serializers.CharField())


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField(required=False)
    current_version = serializers.IntegerField(required=False)


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}
