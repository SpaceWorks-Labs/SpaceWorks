"""Account departure request and response contracts."""

from rest_framework import serializers


class AccountDeletionBlockerSerializer(serializers.Serializer):
    code = serializers.CharField()
    makerspace_id = serializers.IntegerField(allow_null=True)
    makerspace_slug = serializers.CharField(allow_null=True)
    makerspace_member_url = serializers.CharField(allow_null=True)
    organization_url = serializers.CharField(allow_null=True)
    organization_id = serializers.IntegerField(allow_null=True)
    count = serializers.IntegerField(min_value=1)
    detail = serializers.CharField()


class AccountDeletionReauthSerializer(serializers.Serializer):
    required = serializers.BooleanField()
    methods = serializers.ListField(child=serializers.CharField())


class AccountDeletionPreviewSerializer(serializers.Serializer):
    deletable = serializers.BooleanField()
    restorable = serializers.BooleanField()
    restore_reason = serializers.CharField()
    blockers = AccountDeletionBlockerSerializer(many=True)
    reauth = AccountDeletionReauthSerializer()


class AccountDeletionRequestSerializer(serializers.Serializer):
    confirm = serializers.ChoiceField(choices=["DELETE"])


class AccountDeletionResultSerializer(serializers.Serializer):
    deleted_at = serializers.DateTimeField()
    purge_after = serializers.DateTimeField()


class AccountDeletionRefusedSerializer(serializers.Serializer):
    blockers = AccountDeletionBlockerSerializer(many=True)
