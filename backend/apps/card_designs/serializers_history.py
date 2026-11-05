"""Serializers for version history, the "Preview as" holder picker, sheet previews and calibration."""
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin


class CardDesignRevisionSerializer(serializers.Serializer):
    revision = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    created_by = serializers.CharField(allow_blank=True)
    is_current = serializers.BooleanField()
    is_published = serializers.BooleanField()
    review = serializers.CharField(allow_blank=True, help_text="pending | approved | rejected | withdrawn, or blank.")
    layers = serializers.IntegerField(help_text="Layers on both sides of this revision.")


class CardDesignRevisionPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = CardDesignRevisionSerializer(many=True)


class CardDesignRevisionDetailSerializer(CardDesignRevisionSerializer):
    document = serializers.JSONField()


class CardDesignRestoreSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1, help_text="The design's CURRENT revision (compare-and-swap).")


class CardHolderSampleSerializer(PiiMaskingSerializerMixin, serializers.Serializer):
    """A "Preview as" row. Rows are plain dicts, so the space comes from the context."""
    pii_account_fields = ("name",)
    id = serializers.IntegerField()
    kind = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    number = serializers.CharField(allow_blank=True)
    label = serializers.CharField(allow_blank=True)

    def to_representation(self, instance):
        from apps.accounts.pii_presentation import is_platform_superadmin, mask_data, pii_visible
        data = serializers.Serializer.to_representation(self, instance)
        viewer = getattr(self.context.get("request"), "user", None)
        if is_platform_superadmin(viewer) and not pii_visible(viewer, self.context.get("makerspace_id")):
            if mask_data(data, self.pii_account_fields):
                data["pii_masked"] = True
        return data


class SheetPreviewRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("active", "all"), default="active")
    card_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=1000)
    plan_id = serializers.IntegerField(required=False, min_value=1)
    expiring_within_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    paper = serializers.ChoiceField(choices=("a4", "letter"), default="a4")
    order = serializers.ChoiceField(choices=("duplex", "fronts_then_backs"), default="duplex")
    crop_marks = serializers.BooleanField(default=True)


class SheetPreviewSerializer(serializers.Serializer):
    total = serializers.IntegerField(help_text="Cards the job would print.")
    per_page = serializers.IntegerField()
    sheets = serializers.IntegerField(help_text="Sheets of paper (fronts; backs add as many again).")
    paper = serializers.CharField()
    order = serializers.CharField()
    front = serializers.CharField(allow_null=True, help_text="PNG data URI of the first sheet's fronts.")
    back = serializers.CharField(allow_null=True, help_text="PNG data URI of the same sheet's backs, mirrored.")
    mixed_sizes = serializers.BooleanField(help_text="Some cards use a different stock and print on their own sheets.")
