"""Response and request shapes of the space-control API (documented in OpenAPI)."""

from rest_framework import serializers

STATES = ("active", "read_only", "suspended", "archived", "scheduled", "importing", "aborted")


class SpaceHealthUsageRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    used = serializers.IntegerField(allow_null=True)
    limit = serializers.IntegerField(allow_null=True)
    unit = serializers.CharField(help_text="`bytes` or `count`.")
    percent = serializers.FloatField(allow_null=True)


class SpaceHealthUsageSerializer(serializers.Serializer):
    managed = serializers.BooleanField()
    resources = SpaceHealthUsageRowSerializer(many=True)


class SpaceSuspensionSerializer(serializers.Serializer):
    at = serializers.DateTimeField()
    reason = serializers.CharField()
    by = serializers.CharField(allow_null=True)


class SpaceReadOnlyStateSerializer(SpaceSuspensionSerializer):
    source = serializers.ChoiceField(choices=("manual", "trial_expired", "payment_overdue"))


class SpaceScheduleStateSerializer(serializers.Serializer):
    archive_on = serializers.DateTimeField(allow_null=True)
    purge_due_at = serializers.DateTimeField(allow_null=True)
    purge_grace_days = serializers.IntegerField()
    note = serializers.CharField(allow_blank=True)
    scheduled_by = serializers.CharField(allow_null=True)
    scheduled_at = serializers.DateTimeField(allow_null=True)
    reminders_sent = serializers.ListField(child=serializers.CharField())


class SpaceHealthDrillSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=("passed", "failed"))
    finished_at = serializers.DateTimeField(allow_null=True)


class SpaceHealthBackupsSerializer(serializers.Serializer):
    last_backed_up_at = serializers.DateTimeField(allow_null=True)
    last_drill = SpaceHealthDrillSerializer(allow_null=True)


class SpaceHealthSecuritySerializer(serializers.Serializer):
    blocked_accounts = serializers.IntegerField()
    locked_settings = serializers.IntegerField()


class SpaceHealthManagerSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_blank=True)


class SpaceHealthPlanSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)


class SpaceHealthProblemSerializer(serializers.Serializer):
    key = serializers.CharField()
    status = serializers.ChoiceField(choices=("ok", "warn", "error"))
    message = serializers.CharField()
    fix_url = serializers.CharField(allow_blank=True, allow_null=True)


class HealthCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    public_code = serializers.CharField()
    state = serializers.ChoiceField(choices=STATES)
    lifecycle_state = serializers.CharField()
    created_at = serializers.DateTimeField()
    archived_at = serializers.DateTimeField(allow_null=True)
    suspended = SpaceSuspensionSerializer(allow_null=True)
    read_only = SpaceReadOnlyStateSerializer(allow_null=True)
    schedule = SpaceScheduleStateSerializer(allow_null=True)
    usage = SpaceHealthUsageSerializer()
    usage_peak_percent = serializers.FloatField(allow_null=True)
    last_activity_at = serializers.DateTimeField(allow_null=True)
    backups = SpaceHealthBackupsSerializer()
    security = SpaceHealthSecuritySerializer()
    open_issues = serializers.IntegerField()
    modules = serializers.ListField(child=serializers.CharField())
    managers = SpaceHealthManagerSerializer(many=True)
    hosting_type = serializers.ChoiceField(choices=["own", "hosted"], help_text="Decision 236: the stored type.")
    hosted = serializers.BooleanField(help_text="Limits, plans and hosting billing apply now (hosted and hosting on).")
    plan = SpaceHealthPlanSerializer(
        allow_null=True, required=False,
        help_text="Present only while MANAGED_PLANS_ENABLED is on (the managed-hosting limiter, #187A).")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "plan" not in instance:
            data.pop("plan", None)
        return data


class HealthCardDetailSerializer(HealthCardSerializer):
    problems = SpaceHealthProblemSerializer(many=True)


class SpaceControlReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=500)


class SpaceControlEmptySerializer(serializers.Serializer):
    pass


class SpaceScheduleRequestSerializer(serializers.Serializer):
    archive_on = serializers.DateTimeField(required=False, allow_null=True, default=None)
    purge_grace_days = serializers.IntegerField(min_value=1, max_value=3650, default=90)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    confirm_slug = serializers.CharField(max_length=50)


class SpacePurgeRequestSerializer(serializers.Serializer):
    confirm_slug = serializers.CharField(max_length=50)


class SpaceTransferRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    previous_membership_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    previous_outcome = serializers.ChoiceField(choices=("keep_staff", "revoke", "keep_manager"), default="keep_staff")
    previous_roles = serializers.ListField(child=serializers.CharField(max_length=64), required=False, default=list)


class SpaceTransferResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("transferred", "invited"))
    card = HealthCardSerializer()
    invitation_email_status = serializers.CharField(required=False, allow_null=True)
