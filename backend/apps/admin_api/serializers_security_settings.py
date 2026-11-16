"""Request/response shapes for per-space security settings and superadmin PII windows."""

from rest_framework import serializers


class SecurityLockSerializer(serializers.Serializer):
    floor = serializers.JSONField()
    note = serializers.CharField(allow_blank=True)
    locked_at = serializers.DateTimeField()


class SecuritySettingSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    kind = serializers.ChoiceField(choices=["bool", "int", "choice", "list"])
    default = serializers.JSONField()
    choices = serializers.ListField(child=serializers.JSONField())
    value = serializers.JSONField()
    strict_value = serializers.BooleanField(
        allow_null=True, help_text="For an on/off setting, the stricter value a platform lock forces; null otherwise.")
    lock = SecurityLockSerializer(allow_null=True)


class SecuritySettingsSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    settings = SecuritySettingSerializer(many=True)
    can_edit = serializers.BooleanField(help_text="This space's Space Manager or a platform superadmin.")
    can_lock = serializers.BooleanField(help_text="Platform superadmins only.")
    edited_as = serializers.ChoiceField(choices=["space", "platform"], allow_null=True)


class SecuritySettingsUpdateSerializer(serializers.Serializer):
    values = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Setting key -> new value, e.g. {\"security.staff_session_max_hours\": 24}. Applied atomically. "
                  "Staff MFA is not a setting: it is required for every staff role (platform rule, #62).",
    )


class SecurityLockRequestSerializer(serializers.Serializer):
    floor = serializers.JSONField(help_text="The floor the space may not go below; a boolean lock is always true.")
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class PiiAccessOpenSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=300)


class PiiAccessGrantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    scope = serializers.ChoiceField(choices=["space", "person"])
    reason = serializers.CharField()
    opened_by = serializers.CharField(help_text="Display name of the superadmin who opened it.")
    opened_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    close_reason = serializers.CharField(allow_blank=True)
    is_own = serializers.BooleanField()


class PiiAccessStatusSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    viewer_is_superadmin = serializers.BooleanField()
    pii_visible = serializers.BooleanField(help_text="Whether this viewer currently sees this space's PII unmasked.")
    active = PiiAccessGrantSerializer(allow_null=True, help_text="The viewer's own open window here, if any.")
    space_grants = PiiAccessGrantSerializer(many=True, help_text="Open windows on this space, newest first.")
    recent = PiiAccessGrantSerializer(many=True, help_text="The ten most recent windows on this space.")
