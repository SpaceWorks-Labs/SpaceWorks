"""Typed request/response shapes for card routes that answer plain dicts (#193 OpenAPI contract).

These describe what the views already return, so the schema and the generated client stop
reading them as "any object". They are documentation serializers: views keep building
their dicts, and nothing here validates or writes.
"""
from rest_framework import serializers

from .serializers import CardDesignSerializer


class StagedUploadSerializer(serializers.Serializer):
    """A presigned upload to the private staging key (PUT with headers, or a form POST)."""
    url = serializers.URLField()
    method = serializers.CharField(required=False, help_text='"PUT"; absent for a form POST.')
    headers = serializers.DictField(child=serializers.CharField(), required=False)
    fields = serializers.DictField(child=serializers.CharField(), required=False,
                                   help_text="Form fields for a POST upload.")


class CardAssetUploadSerializer(StagedUploadSerializer):
    asset_id = serializers.CharField()


class PhotoUploadSerializer(StagedUploadSerializer):
    object_key = serializers.CharField()
    content_type = serializers.CharField()


class FontPrepareRequestSerializer(serializers.Serializer):
    family = serializers.CharField()


class FontPrepareResultSerializer(serializers.Serializer):
    family = serializers.CharField()
    pending_weights = serializers.ListField(child=serializers.IntegerField())
    state = serializers.CharField()


class PhotoSetSerializer(serializers.Serializer):
    photo_set = serializers.BooleanField()


class QueuedSerializer(serializers.Serializer):
    queued = serializers.BooleanField()


class CheckLinkSerializer(serializers.Serializer):
    check_url = serializers.URLField()
    reprint_needed = serializers.CharField()


class CardFaceSerializer(serializers.Serializer):
    document = serializers.JSONField(help_text="The published, normalised design document.")
    values = serializers.DictField(child=serializers.CharField(allow_blank=True))
    photo = serializers.CharField(allow_null=True, help_text="A data: URI, or null.")
    photo_cutout = serializers.CharField(allow_null=True, help_text="The ready cut-out (PNG with alpha) as a data: URI "
                                         "when the design has a photo layer that asks for one, else null.")
    use_cutout = serializers.BooleanField(help_text="The holder chose their cut-out (photo layer variant `auto`).")
    logos = serializers.DictField(child=serializers.CharField(allow_null=True))
    assets = serializers.DictField(child=serializers.CharField(allow_null=True))
    desk_qr = serializers.CharField(allow_null=True)
    verify_qr = serializers.CharField(allow_null=True)
    checkin_qr = serializers.CharField(allow_null=True)
    barcodes = serializers.DictField(child=serializers.CharField(allow_null=True),
                                     help_text="Code128 SVG data URIs by source: number, desk.")


class PhotoDecisionResultSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class CardDesignFileSerializer(serializers.Serializer):
    kind = serializers.CharField()
    version = serializers.IntegerField()
    domain = serializers.CharField()
    document = serializers.JSONField()


class CardDesignPairSerializer(serializers.Serializer):
    """The designs an event uses; a domain switched off for the space is absent."""
    event_card = CardDesignSerializer(required=False)
    event_ticket = CardDesignSerializer(required=False)


class ApprovalLevelSerializer(serializers.Serializer):
    required = serializers.BooleanField(allow_null=True, help_text="Set here; null follows the level above.")
    inherited = serializers.BooleanField(allow_null=True, help_text="What null currently means.")


class ApprovalLevelRequestSerializer(serializers.Serializer):
    required = serializers.BooleanField(allow_null=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)


class CreatedIdSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class CreatedNoteSerializer(CreatedIdSerializer):
    created_at = serializers.DateTimeField()


class PresenceCheckInResultSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    account_id = serializers.IntegerField()
