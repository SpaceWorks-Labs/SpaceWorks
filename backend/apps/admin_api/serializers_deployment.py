"""Explicit safe read contract; storage identities and credentials have no field."""
from rest_framework import serializers


class UsageSampleSerializer(serializers.Serializer):
    used = serializers.IntegerField(allow_null=True)
    cap = serializers.IntegerField(allow_null=True)
    unit = serializers.ChoiceField(choices=["bytes", "recipients"])
    state = serializers.ChoiceField(choices=["ok", "warning", "critical", "reached", "unknown", "stale"])
    source = serializers.CharField()
    cap_source = serializers.CharField()
    cap_verified_on = serializers.DateField(allow_null=True)
    scope = serializers.ChoiceField(choices=["deployment", "tenant", "provider_account"])
    sampled_at = serializers.DateTimeField(allow_null=True)
    uncertain = serializers.IntegerField()
    reason_code = serializers.CharField(allow_blank=True)


class TickStatusSerializer(serializers.Serializer):
    last_completed_at = serializers.DateTimeField(allow_null=True)
    last_contact_at = serializers.DateTimeField(allow_null=True)
    age_seconds = serializers.IntegerField(allow_null=True)
    interval_seconds = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["ok", "late", "never", "failed", "unknown"])
    failed_tasks = serializers.IntegerField()


class FreeUsageSerializer(serializers.Serializer):
    profile = serializers.ChoiceField(choices=["free"])
    visibility = serializers.ChoiceField(choices=["deployment", "tenant"])
    database = UsageSampleSerializer(allow_null=True)
    objects = UsageSampleSerializer()
    email = UsageSampleSerializer()
    email_pending = serializers.IntegerField(allow_null=True)
    email_uncertain = serializers.IntegerField(allow_null=True)
    tick = TickStatusSerializer()
    notices = serializers.ListField(child=serializers.CharField())


class StorageGuaranteeSerializer(serializers.Serializer):
    label = serializers.CharField()
    upload = serializers.ChoiceField(choices=["put", "post"])
    versioned = serializers.BooleanField()
    object_lock = serializers.BooleanField()


class ProviderRecoverySerializer(serializers.Serializer):
    database_status = serializers.ChoiceField(choices=["verified", "unavailable", "unknown"])
    object_status = serializers.ChoiceField(choices=["verified", "unavailable", "unknown"])
    drill_status = serializers.ChoiceField(choices=["verified", "failed", "never", "unknown"])
    last_drill_at = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField()
    runbook_url = serializers.URLField(required=False)


class DeploymentNoticeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["host", "managed"])
    profile = serializers.ChoiceField(choices=["full", "free"])
    scanner = serializers.ChoiceField(choices=["none", "clamav"])
    media_validation_available = serializers.BooleanField()


class DeploymentSummarySerializer(DeploymentNoticeSerializer):
    scope = serializers.ChoiceField(choices=["deployment"])
    topology = serializers.CharField()
    database_transport = serializers.CharField()
    database_major = serializers.IntegerField()
    storage = StorageGuaranteeSerializer(many=True)
    last_worker_success_at = serializers.DateTimeField(allow_null=True)
    last_scheduler_success_at = serializers.DateTimeField(allow_null=True)
    portable_dump_available = serializers.BooleanField()
    portable_dump_reason = serializers.CharField(required=False)
    provider_recovery = ProviderRecoverySerializer(required=False)
    free_usage = FreeUsageSerializer(required=False)


class TenantDeploymentSerializer(DeploymentNoticeSerializer):
    scope = serializers.ChoiceField(choices=["tenant"])
    deployment_warning = serializers.BooleanField()
    objects = UsageSampleSerializer(required=False)
