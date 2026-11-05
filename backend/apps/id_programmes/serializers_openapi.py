"""Typed shapes for ID-programme routes that answer plain dicts (#193 OpenAPI contract)."""
from rest_framework import serializers

from .serializers import PublicProgrammeSerializer

STATES = ("signed_out", "open", "closed", "waiting", "approved", "not_approved", "revoked")


class DecisionResultSerializer(serializers.Serializer):
    changed = serializers.IntegerField()


class SkippedRowSerializer(serializers.Serializer):
    row = serializers.IntegerField(help_text="Counted from 2, after the header row.")
    reason = serializers.ChoiceField(choices=("no_name", "bad_email", "duplicate_in_file", "already_in_programme"))


class ImportPreviewResultSerializer(serializers.Serializer):
    headers = serializers.ListField(child=serializers.CharField())
    rows = serializers.ListField(child=serializers.ListField(child=serializers.CharField(allow_blank=True)))
    mapping = serializers.DictField(child=serializers.IntegerField(allow_null=True),
                                    help_text="Field -> column index, or null when unmapped.")
    rows_total = serializers.IntegerField()
    to_create = serializers.IntegerField()
    skipped = SkippedRowSerializer(many=True)
    source = serializers.CharField(required=False, help_text="Present for a Google Sheet import.")
    sheet_sha256 = serializers.CharField(required=False)


class ImportCommitResultSerializer(serializers.Serializer):
    rows_total = serializers.IntegerField()
    created = serializers.IntegerField()
    would_create = serializers.IntegerField()
    skipped = SkippedRowSerializer(many=True)
    dry_run = serializers.BooleanField()


class IdProgrammeDetailSerializer(PublicProgrammeSerializer):
    state = serializers.ChoiceField(choices=STATES, read_only=True)

    class Meta(PublicProgrammeSerializer.Meta):
        fields = (*PublicProgrammeSerializer.Meta.fields, "state")
        read_only_fields = fields


class JoinResultSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=STATES)
    card_id = serializers.IntegerField()


class PrefillSerializer(serializers.Serializer):
    values = serializers.DictField(child=serializers.CharField(), help_text="Question key -> saved value.")


class JoinPhotoRequestSerializer(serializers.Serializer):
    content_type = serializers.CharField()


class InviteAcceptResultSerializer(serializers.Serializer):
    card_id = serializers.IntegerField()
    status = serializers.CharField()
