from django.utils.translation import gettext
from rest_framework import serializers

from apps.boxes.serializers import QrCodeSerializer


class ExternalQrNewAssetSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    asset_tag = serializers.CharField(max_length=100)
    serial_number = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ExternalQrAssignSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    # Capped generously here; the service applies the real 64-character rule with a
    # message staff can act on.
    value = serializers.CharField(max_length=512, trim_whitespace=False, allow_blank=True)
    product_id = serializers.IntegerField(required=False)
    asset_id = serializers.IntegerField(required=False)
    create_product = serializers.DictField(
        required=False,
        help_text=(
            "Create a quantity-tracked product (same fields as the admin inventory create "
            "route) and link the code to it in one transaction."
        ),
    )
    create_asset = ExternalQrNewAssetSerializer(
        required=False,
        help_text="Create a unit under an individual-tracked product and link the code to it.",
    )

    def validate(self, attrs):
        chosen = [key for key in ("product_id", "asset_id", "create_product", "create_asset") if attrs.get(key)]
        if len(chosen) != 1:
            raise serializers.ValidationError(gettext(
                "Provide exactly one of product_id, asset_id, create_product or create_asset."))
        return attrs


class ExternalQrAssignResultSerializer(serializers.Serializer):
    qr = QrCodeSerializer()
    target = serializers.DictField()
    created = serializers.BooleanField(help_text="False when the code was already linked to this target.")


class ExternalQrConflictSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=["already_assigned", "revoked", "target_has_qr"])
    detail = serializers.CharField()
    qr_id = serializers.IntegerField(required=False)
    target = serializers.DictField(required=False, help_text="The item the code is already linked to.")
