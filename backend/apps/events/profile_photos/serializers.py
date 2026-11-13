from django.utils.translation import gettext
from rest_framework import serializers
from apps.events.serializers_staff_tools import StrictSerializer


class PresentationWriteSerializer(StrictSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)
    profile_id = serializers.IntegerField(min_value=1, allow_null=True)
    membership_id = serializers.IntegerField(min_value=1, allow_null=True)
    source_revision = serializers.CharField(max_length=64, allow_null=True)
    print_photo_consent = serializers.BooleanField(default=False)
    public_card_consent = serializers.BooleanField(default=False)
    public_card_scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=("team", "mentor", "judge")), max_length=3, default=list,
    )

    def validate(self, data):
        if (data["profile_id"] is None) != (data["membership_id"] is None):
            raise serializers.ValidationError(gettext("Select a matching profile and membership."))
        scopes = data["public_card_scopes"]
        if len(scopes) != len(set(scopes)):
            raise serializers.ValidationError({"public_card_scopes": gettext("Choose each scope once.")})
        if not data["public_card_consent"] and scopes:
            raise serializers.ValidationError({"public_card_scopes": gettext("Enable public card consent first.")})
        if data["profile_id"] is None and (data["source_revision"] is not None
                or data["print_photo_consent"] or data["public_card_consent"] or scopes):
            raise serializers.ValidationError(gettext("No profile must also clear all photo and card consents."))
        return data


class PresentationSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()
    profile_id = serializers.IntegerField(allow_null=True)
    membership_id = serializers.IntegerField(allow_null=True)
    source_revision = serializers.CharField(allow_null=True)
    print_photo_consent = serializers.BooleanField()
    public_card_consent = serializers.BooleanField()
    public_card_scopes = serializers.ListField(child=serializers.CharField())


class ProfileOptionSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    profile_id = serializers.IntegerField()
    makerspace_name = serializers.CharField()
    has_photo = serializers.BooleanField()
    source_revision = serializers.CharField()
    public_eligible = serializers.BooleanField()


class ProfileOptionsSerializer(serializers.Serializer):
    selected_profile_id = serializers.IntegerField(allow_null=True)
    options = ProfileOptionSerializer(many=True)
    no_photo_allowed = serializers.BooleanField()
