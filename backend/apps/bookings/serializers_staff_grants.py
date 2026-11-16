from django.utils.translation import gettext
from rest_framework import serializers

from .booking_permissions import PERMISSIONS
from .models_staff_grants import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite


class GrantedBookingEntrySerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    makerspace_id = serializers.IntegerField()
    makerspace_slug = serializers.CharField()
    name = serializers.CharField()
    source = serializers.ChoiceField(choices=["booking_grant"])
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSIONS))


class BookingStaffGrantPermissionsSerializer(serializers.Serializer):
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=PERMISSIONS), min_length=1, max_length=4,
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(set(data) - set(self.fields))})
        return super().to_internal_value(data)

    def validate_permissions(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(gettext("Permissions must be distinct."))
        return sorted(value)


class BookingStaffGrantInviteInputSerializer(BookingStaffGrantPermissionsSerializer):
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    send_email = serializers.BooleanField(default=False)


class BookingStaffGrantSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSIONS),
                                        min_length=1, max_length=4, read_only=True)

    class Meta:
        model = BookingSpaceStaffGrant
        fields = ("id", "makerspace", "space", "user", "permissions",
                  "granted_by", "created_at", "revoked_at", "revoked_by")
        read_only_fields = fields


class BookingStaffGrantInviteSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSIONS),
                                        min_length=1, max_length=4, read_only=True)

    class Meta:
        model = BookingSpaceStaffGrantInvite
        fields = ("id", "makerspace", "space", "permissions", "created_by",
                  "created_at", "expires_at", "redeemed_at", "revoked_at")
        read_only_fields = fields


class BookingStaffGrantInviteCreatedSerializer(BookingStaffGrantInviteSerializer):
    token = serializers.CharField(read_only=True)

    class Meta(BookingStaffGrantInviteSerializer.Meta):
        fields = (*BookingStaffGrantInviteSerializer.Meta.fields, "token")


class BookingStaffGrantRedeemSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=128, write_only=True)


class BookingStaffGrantListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = BookingStaffGrantSerializer(many=True)


class BookingStaffGrantInviteListSerializer(BookingStaffGrantListSerializer):
    results = BookingStaffGrantInviteSerializer(many=True)
