"""OpenAPI shapes for the image-adapter provider settings, cut-outs and the bulk photo batches."""
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


class ImageAdapterInputSerializer(serializers.Serializer):
    provider_url = serializers.CharField(max_length=300, required=False, allow_blank=True)
    secret = serializers.CharField(max_length=200, required=False, allow_blank=True, write_only=True, trim_whitespace=False)
    clear = serializers.BooleanField(required=False)
    use_platform_provider = serializers.BooleanField(required=False)


class ImageAdapterSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    provider_url = serializers.CharField(allow_blank=True)
    fingerprint = serializers.CharField(allow_blank=True)
    last_test_at = serializers.DateTimeField(allow_null=True)
    last_test_ok = serializers.BooleanField(allow_null=True)
    last_test_error = serializers.CharField(allow_blank=True)


class SpaceImageAdapterSerializer(ImageAdapterSerializer):
    use_platform_provider = serializers.BooleanField()
    platform_available = serializers.BooleanField()
    effective = serializers.ChoiceField(choices=("space", "platform"), allow_null=True)


class ImageAdapterTestSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    error = serializers.CharField(allow_blank=True)
    tested_at = serializers.DateTimeField()


class CutoutRequestSerializer(serializers.Serializer):
    consent = serializers.BooleanField(required=False, default=False)


class CutoutUseSerializer(serializers.Serializer):
    use = serializers.ChoiceField(choices=("cutout", "original"))


class CutoutSerializer(serializers.Serializer):
    available = serializers.BooleanField(help_text="A provider is configured and the switch is on.")
    state = serializers.ChoiceField(choices=("none", "queued", "running", "done", "failed", "stale"))
    error_code = serializers.CharField(allow_blank=True)
    use = serializers.ChoiceField(choices=("cutout", "original"))
    image_url = serializers.CharField(allow_blank=True, help_text="Short-lived private link; empty unless done.")
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    requested_at = serializers.DateTimeField(allow_null=True)
    notice = serializers.CharField(help_text="Decision 345(b): the space's eraser processing notice, shown to members.")
    notice_version = serializers.CharField()
    opted_out = serializers.BooleanField(help_text="The photo's owner opted out: never sent; the original prints.")


class CutoutOptOutSerializer(serializers.Serializer):
    opted_out = serializers.BooleanField()


class BatchCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("member_card", "staff_card", "event_card"))
    event_id = serializers.IntegerField(required=False, allow_null=True)
    holders_consented = serializers.BooleanField()
    remove_backgrounds = serializers.BooleanField(required=False, default=False)


class BatchApplySerializer(serializers.Serializer):
    remove_backgrounds = serializers.BooleanField(required=False, help_text="Queue an eraser job per applied photo.")


class BatchFilesSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False, max_length=50)


class BatchItemChoiceSerializer(serializers.Serializer):
    holder_id = serializers.IntegerField(required=False, allow_null=True)
    decision = serializers.ChoiceField(choices=("apply", "replace", "keep", "skip"), required=False)


class BatchItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    filename = serializers.CharField()
    status = serializers.ChoiceField(choices=("matched", "ambiguous", "unmatched", "has_photo"))
    match_kind = serializers.CharField(allow_blank=True)
    holder_id = serializers.IntegerField(allow_null=True)
    holder_name = serializers.CharField(allow_blank=True)
    candidates = serializers.ListField(child=serializers.DictField())
    decision = serializers.CharField()
    state = serializers.CharField()
    error_code = serializers.CharField(allow_blank=True)
    thumbnail_url = serializers.CharField(allow_blank=True)


@extend_schema_serializer(component_name="PhotoBatch")
class BatchSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    event_id = serializers.IntegerField(allow_null=True)
    state = serializers.CharField()
    remove_backgrounds = serializers.BooleanField()
    eraser_available = serializers.BooleanField()
    file_count = serializers.IntegerField()
    applied_count = serializers.IntegerField()
    skipped_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    expires_at = serializers.DateTimeField()
    items = BatchItemSerializer(many=True)
    holders = serializers.ListField(child=serializers.DictField(), help_text="Holders to pick from (id, name, number).")
