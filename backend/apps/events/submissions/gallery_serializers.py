"""Explicit public selection and privacy-withdrawal command schemas."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.events.judging.serializers import CommandInput, IdList


class GalleryGrantInput(CommandInput):
    snapshot_id = serializers.IntegerField(min_value=1)
    metadata_public = serializers.BooleanField()
    asset_ids = IdList(default=list)
    link_ids = IdList(default=list)
    consent = serializers.BooleanField()

    def validate(self, attrs):
        if self.initial_data.get("consent") is not True or not attrs["metadata_public"]:
            raise serializers.ValidationError({"consent": "explicit_consent_required"})
        return attrs


class GalleryWithdrawInput(CommandInput):
    scope = serializers.CharField(max_length=8)
    asset_ids = IdList(default=list)
    link_ids = IdList(default=list)

    def validate(self, attrs):
        has_items = bool(attrs["asset_ids"] or attrs["link_ids"])
        if (attrs["scope"] not in ("all", "items") or (attrs["scope"] == "items" and not has_items)
                or (attrs["scope"] == "all" and has_items)):
            from apps.events.judging.errors import ProgrammeError
            raise ProgrammeError("invalid_consent_scope", gettext("Choose all disclosure or a nonempty item selection."), status=400)
        return attrs


class GalleryPublishInput(CommandInput):
    snapshot_ids = IdList(allow_empty=False)
    result_revision_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)


class GalleryHideInput(CommandInput):
    hidden = serializers.BooleanField(default=True)
    reason = serializers.CharField(max_length=2000)


class GalleryAmendInput(CommandInput):
    snapshot_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000)


class GalleryResultCorrectionInput(CommandInput):
    result_revision_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000)
