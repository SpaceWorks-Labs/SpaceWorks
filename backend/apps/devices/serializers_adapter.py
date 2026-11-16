"""Staff-side contracts for the Device Adapter API: strict, bounded, no secret ever echoed."""
from drf_spectacular.utils import extend_schema_serializer
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.devices.adapters.registry import CAPABILITIES
from apps.devices.models import AdapterBinding, AdapterCommand, AdapterCredential, AdapterEvent, AdapterPose, AdapterWatch
from apps.devices.serializers_identity import StrictSerializer

CAPABILITY_CHOICES = sorted(CAPABILITIES)
TARGET_CHOICES = [value for value, _label in AdapterBinding.TargetType.choices]


class AdapterEnrollSerializer(StrictSerializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    offline_threshold_seconds = serializers.IntegerField(min_value=1, max_value=7 * 24 * 3600, required=False,
                                                         default=300)


@extend_schema_serializer(component_name="AdapterBindingCreate")
class BindingCreateSerializer(StrictSerializer):
    target_type = serializers.ChoiceField(choices=TARGET_CHOICES)
    machine_id = serializers.IntegerField(min_value=1, required=False)
    target_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    external_ref = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    capabilities = serializers.ListField(child=serializers.ChoiceField(choices=CAPABILITY_CHOICES), max_length=32,
                                         allow_empty=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["target_type"] == "machine" and "machine_id" not in attrs:
            raise serializers.ValidationError({"machine_id": gettext("Required for a machine target.")})
        return attrs


@extend_schema_serializer(component_name="AdapterBinding")
class BindingSerializer(serializers.ModelSerializer):
    """A binding as staff see it: ``config`` is its own overrides, ``effective_config`` maps each key to
    ``{value, source}`` with source ``type`` (follows the machine-type profile) or ``binding`` (overridden)."""

    config = serializers.SerializerMethodField()
    effective_config = serializers.SerializerMethodField()

    class Meta:
        model = AdapterBinding
        fields = ("id", "device", "target_type", "machine", "target_id", "external_ref", "capabilities", "enabled",
                  "created_at", "config", "effective_config")
        read_only_fields = fields

    def _view(self, obj):
        from apps.devices.services_adapter_safety import config_view
        return config_view(obj)

    @extend_schema_field(serializers.DictField())
    def get_config(self, obj):
        return self._view(obj)["config"]

    @extend_schema_field(serializers.DictField())
    def get_effective_config(self, obj):
        return self._view(obj)["effective_config"]


class CommandCreateSerializer(StrictSerializer):
    capability = serializers.ChoiceField(choices=CAPABILITY_CHOICES)
    command = serializers.CharField(max_length=32)
    params = serializers.DictField(required=False, default=dict)


@extend_schema_serializer(component_name="AdapterCommand")
class CommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterCommand
        # Params are omitted: a pose is staff-only calibration data and need not be re-served in a log.
        fields = ("id", "binding", "capability", "command", "status", "attempts", "result_code", "created_by",
                  "created_at", "completed_at", "expires_at")
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterEvent
        fields = ("id", "binding", "operation_id", "event_type", "capability", "data", "observed_at", "received_at")
        read_only_fields = fields


class PoseWriteSerializer(StrictSerializer):
    target_type = serializers.ChoiceField(choices=["storage_location", "item", "box"])
    target_id = serializers.CharField(max_length=64)
    pose = serializers.DictField()
    note = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class PoseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterPose
        fields = ("id", "binding", "target_type", "target_id", "pose", "note", "saved_by", "updated_at")
        read_only_fields = fields


class PoseKeySerializer(StrictSerializer):
    target_type = serializers.ChoiceField(choices=["storage_location", "item", "box"])
    target_id = serializers.CharField(max_length=64)


class AimSerializer(StrictSerializer):
    pose = serializers.DictField()


class JogSerializer(StrictSerializer):
    dx = serializers.FloatField(required=False, default=0, min_value=-1000, max_value=1000)
    dy = serializers.FloatField(required=False, default=0, min_value=-1000, max_value=1000)


class IndicateSerializer(StrictSerializer):
    mode = serializers.ChoiceField(choices=["point", "light", "clear"], default="point")
    target_type = serializers.ChoiceField(choices=["storage_location", "item", "box"], required=False, default="item")
    target_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    duration_seconds = serializers.IntegerField(min_value=1, max_value=600, required=False, default=10)
    color = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")


class CredentialWriteSerializer(StrictSerializer):
    user_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=["nfc", "pin"])
    secret = serializers.CharField(max_length=64, min_length=4, write_only=True, trim_whitespace=True)
    label = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


class CredentialSerializer(serializers.ModelSerializer):
    """Never carries the secret or its digest."""

    class Meta:
        model = AdapterCredential
        fields = ("id", "user", "kind", "label", "locked_until", "last_used_at", "disabled_at", "created_at")
        read_only_fields = fields


class WatchStartSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    record = serializers.BooleanField(required=False, default=False)  # opt-in recording
    audio = serializers.BooleanField(required=False, default=False)  # receive-only audio track (decision 321a)
    talk = serializers.BooleanField(required=False, default=False)  # staff push-to-talk (implies audio)
    notice_ack = serializers.BooleanField(required=False, default=False)  # audio-recording notice acknowledged


class WatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterWatch
        fields = ("id", "binding", "status", "record", "audio", "talk", "audio_notice_ack", "expires_at", "created_at",
                  "ended_at")
        read_only_fields = fields


@extend_schema_serializer(component_name="AdapterJobCreate")
class JobCreateSerializer(StrictSerializer):
    service_request_id = serializers.IntegerField(min_value=1)


class BindingConfigSerializer(StrictSerializer):
    """Server-enforced safety config of a binding (see ``caps/safety.py``)."""

    auto_off_idle_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    require_area_clear = serializers.BooleanField(required=False)
    max_session_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    require_filter_ok = serializers.BooleanField(required=False)
    auto_apply_terminal = serializers.BooleanField(required=False)  # a clean terminal report skips staff review
    laser_max_power_pct = serializers.IntegerField(min_value=1, max_value=100, required=False)  # shelf pointer cap
    max_on_seconds = serializers.IntegerField(min_value=1, max_value=600, required=False)  # shelf pointer cap


class TypeProfileSerializer(StrictSerializer):
    """Safety defaults for every adapter binding on machines of one type (a binding's own config overrides them)."""

    auto_off_idle_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    require_area_clear = serializers.BooleanField(required=False)
    max_session_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    require_filter_ok = serializers.BooleanField(required=False)


class WebhookWriteSerializer(StrictSerializer):
    url = serializers.URLField(max_length=500)
    include_data = serializers.BooleanField(required=False, default=False)
