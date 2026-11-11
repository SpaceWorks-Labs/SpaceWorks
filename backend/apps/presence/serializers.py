from django.utils.translation import gettext
from math import isfinite

from rest_framework import serializers
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field

from .models import PresenceSession
from .privacy import settings_for


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            unknown = set(data.keys()) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unknown field." for key in unknown})
        return super().to_internal_value(data)


class PresenceRenewSerializer(StrictSerializer):
    duration_minutes = serializers.IntegerField(min_value=15, max_value=480)


class PresenceStartSerializer(PresenceRenewSerializer):
    status = serializers.ChoiceField(choices=["working", "visiting", "guest"], required=False)
    project_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    hide_on_display = serializers.BooleanField(required=False)
    latitude = serializers.FloatField(required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, min_value=-180, max_value=180)
    accuracy = serializers.FloatField(required=False, min_value=0)

    def validate(self, attrs):
        for key in ("latitude", "longitude", "accuracy"):
            if key in attrs and not isfinite(attrs[key]):
                raise serializers.ValidationError({key: gettext("Provide a finite number.")})
        return attrs


class StaffPresenceStartSerializer(PresenceStartSerializer):
    account_id = serializers.IntegerField(min_value=1)
    # Decision 223 (j): staff witnessed the guest accept the waiver; stamped on their pass, audited.
    waiver_accepted_at_desk = serializers.BooleanField(required=False, default=False)


class StaffPresenceEndSerializer(StrictSerializer):
    account_id = serializers.IntegerField(min_value=1)


class PresencePrivacySerializer(StrictSerializer):
    show_names = serializers.BooleanField()
    allow_personal_opt_out = serializers.BooleanField()


class PresencePreferenceSerializer(StrictSerializer):
    hide_on_display = serializers.BooleanField()


class PresenceSessionSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()
    names_displayed = serializers.SerializerMethodField()
    personal_opt_out_allowed = serializers.SerializerMethodField()
    project_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = PresenceSession
        fields = ["started_at", "expires_at", "ended_at", "end_reason", "active", "status",
                  "project_id", "hide_on_display", "names_displayed", "personal_opt_out_allowed"]

    @extend_schema_field(serializers.BooleanField)
    def get_active(self, obj):
        return obj.ended_at is None and obj.expires_at > timezone.now()

    @extend_schema_field(serializers.BooleanField)
    def get_names_displayed(self, obj):
        policy = self._display_policy(obj)
        return policy.show_names and not (policy.allow_personal_opt_out and obj.hide_on_display)

    @extend_schema_field(serializers.BooleanField)
    def get_personal_opt_out_allowed(self, obj):
        return self._display_policy(obj).allow_personal_opt_out

    def _display_policy(self, obj):
        if not hasattr(self, "_policies"):
            self._policies = {}
        if obj.makerspace_id not in self._policies:
            self._policies[obj.makerspace_id] = settings_for(obj.makerspace)
        return self._policies[obj.makerspace_id]


class PresenceCurrentSerializer(serializers.Serializer):
    active = serializers.BooleanField()
    session = PresenceSessionSerializer(allow_null=True)
    renewable = PresenceSessionSerializer(allow_null=True, required=False)
    presets = serializers.ListField(child=serializers.IntegerField(), required=False)
    personal_opt_out_allowed = serializers.BooleanField()
    names_displayed = serializers.BooleanField()


class PresenceRosterSerializer(PresenceSessionSerializer):
    display_name = serializers.CharField(source="account.display_name")
    account_id = serializers.IntegerField(read_only=True)
    role_label = serializers.SerializerMethodField()

    class Meta(PresenceSessionSerializer.Meta):
        fields = [*PresenceSessionSerializer.Meta.fields, "account_id", "display_name", "role_label"]

    @extend_schema_field(serializers.CharField)
    def get_role_label(self, obj):
        if obj.membership_id is None:
            return "Guest"
        role = obj.membership.assigned_role
        return role.name if role else obj.membership.get_role_display()


class PresenceRosterPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PresenceRosterSerializer(many=True)
    personal_opt_out_allowed = serializers.BooleanField()
    names_displayed = serializers.BooleanField()


class PresenceProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    public_visible = serializers.BooleanField()


class PresenceProjectPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PresenceProjectSerializer(many=True)


class PresenceTVRowSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    status = serializers.ChoiceField(choices=PresenceSession.Status.choices)
    project_title = serializers.CharField(required=False)
    event_title = serializers.CharField(required=False)
    since = serializers.DateTimeField()
