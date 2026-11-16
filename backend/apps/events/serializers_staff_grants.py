from django.utils.translation import gettext
from rest_framework import serializers

from .event_permissions import PERMISSIONS
from .models import EventStaffGrant, EventStaffGrantInvite
from .models_staff_grants import RoleLabel


class GrantedEventEntrySerializer(serializers.Serializer):
    event_id = serializers.IntegerField(allow_null=True)
    series_id = serializers.IntegerField(allow_null=True)
    makerspace_id = serializers.IntegerField()
    makerspace_slug = serializers.CharField()
    title = serializers.CharField()
    source = serializers.ChoiceField(choices=["event_grant"])
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSIONS))


class StaffGrantPermissionsSerializer(serializers.Serializer):
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=PERMISSIONS), min_length=1, max_length=5,
    )

    def validate_permissions(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(gettext("Permissions must be distinct."))
        return sorted(value)


class StaffGrantUpdateSerializer(StaffGrantPermissionsSerializer):
    # Omitted leaves the label alone; "" clears it. Display only, never authority.
    role_label = serializers.ChoiceField(choices=RoleLabel.choices, allow_blank=True, required=False)


class StaffGrantInviteInputSerializer(StaffGrantPermissionsSerializer):
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    send_email = serializers.BooleanField(default=False)
    role_label = serializers.ChoiceField(choices=RoleLabel.choices, allow_blank=True, default="")
    # Decision 221(i): omitted, a limited co-organizer's invite inherits their own limit; wider is refused.
    track_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list,
                                      max_length=50)
    valid_from = serializers.DateTimeField(required=False, allow_null=True, default=None)
    valid_until = serializers.DateTimeField(required=False, allow_null=True, default=None)


class StaffGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventStaffGrant
        fields = ("id", "makerspace", "event", "series", "user", "permissions", "role_label",
                  "granted_by", "created_at", "revoked_at", "revoked_by")
        read_only_fields = fields


class StaffGrantInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventStaffGrantInvite
        fields = ("id", "makerspace", "event", "series", "permissions", "role_label", "track_ids",
                  "valid_from", "valid_until", "created_by", "created_at", "expires_at", "redeemed_at", "revoked_at")
        read_only_fields = fields


class StaffGrantInviteCreatedSerializer(StaffGrantInviteSerializer):
    token = serializers.CharField(read_only=True)

    class Meta(StaffGrantInviteSerializer.Meta):
        fields = (*StaffGrantInviteSerializer.Meta.fields, "token")


class StaffGrantRedeemSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=128, write_only=True)


class StaffGrantListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = StaffGrantSerializer(many=True)


class StaffGrantInviteListSerializer(StaffGrantListSerializer):
    results = StaffGrantInviteSerializer(many=True)
