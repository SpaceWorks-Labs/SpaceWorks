from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.evidence.serializers import EvidenceUrlResponseSerializer
from apps.inventory.kit_serializers import KitCountsField


class PublicToolScanSerializer(serializers.Serializer):
    kit_checklist = KitCountsField(required=False, default=list)
    payload = serializers.CharField(max_length=64)
    evidence_id = serializers.IntegerField()
    remark = serializers.CharField()
    report_problem = serializers.BooleanField(required=False, default=False)
    problem_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs):
        if attrs.get("report_problem") and not attrs.get("problem_note", "").strip():
            raise serializers.ValidationError(
                {"problem_note": "Problem note is required."}
            )
        return attrs


class PublicToolCheckoutSerializer(serializers.Serializer):
    kit_checklist = KitCountsField(required=False, default=list)
    payload = serializers.CharField(max_length=64)
    evidence_id = serializers.IntegerField()
    remark = serializers.CharField(required=False, allow_blank=True)


class PublicToolEvidenceUrlRequestSerializer(serializers.Serializer):
    evidence_type = serializers.ChoiceField(choices=["issue", "return"])
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class PublicToolLoanItemSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()


class PublicToolLoanSerializer(serializers.Serializer):
    has_kit_checklist = serializers.SerializerMethodField()

    def get_has_kit_checklist(self, obj) -> bool:
        return bool(obj.request.box_issue_checklist or any(item.issue_checklist for item in obj.request.items.all()))

    public_token = serializers.UUIDField(source="request.public_token", read_only=True)
    status = serializers.CharField(read_only=True)
    items = serializers.SerializerMethodField()

    @extend_schema_field(PublicToolLoanItemSerializer(many=True))
    def get_items(self, obj) -> list[dict[str, object]]:
        if "items" in getattr(obj.request, "_prefetched_objects_cache", {}):
            items = sorted(obj.request.items.all(), key=lambda item: item.product.name)
        else:
            items = obj.request.items.select_related("product").order_by("product__name")
        return [
            {"product_name": item.product.name, "quantity": item.issued_quantity}
            for item in items
        ]


class _ContactFields(serializers.Serializer):
    """Account-less self-checkout identity (#91): a space without member accounts."""

    contact_name = serializers.CharField(max_length=200, trim_whitespace=True)
    contact_email = serializers.EmailField(max_length=254)
    contact_phone = serializers.CharField(max_length=32, trim_whitespace=True)
    email_code = serializers.RegexField(r"^\d{6}$", write_only=True)
    evidence_grant = serializers.CharField(max_length=512, write_only=True)


class ContactToolCheckoutSerializer(_ContactFields, PublicToolCheckoutSerializer):
    pass


class ContactToolScanSerializer(_ContactFields, PublicToolScanSerializer):
    pass


class ContactEvidenceUrlRequestSerializer(PublicToolEvidenceUrlRequestSerializer):
    contact_email = serializers.EmailField(max_length=254)


class PublicToolEvidenceUrlResponseSerializer(EvidenceUrlResponseSerializer):
    """The evidence upload URL, plus the grant an account-less borrower sends back."""

    evidence_grant = serializers.CharField(required=False)
