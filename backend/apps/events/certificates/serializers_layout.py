from rest_framework import serializers
from apps.operations.printable_serializers import PrintInputSerializer
from .layout import COLOURS


class CertificateLayerSerializer(PrintInputSerializer):
    id = serializers.UUIDField()
    order = serializers.IntegerField(min_value=0, max_value=19)
    type = serializers.ChoiceField(choices=("text", "image", "logo", "photo", "certificate_id",
                                             "certificate_qr", "event_credential_qr", "signature"))
    x_mm = serializers.FloatField(min_value=0)
    y_mm = serializers.FloatField(min_value=0)
    width_mm = serializers.FloatField(min_value=0.1)
    height_mm = serializers.FloatField(min_value=0.1)
    rotation = serializers.FloatField(min_value=-360, max_value=360, default=0)
    text = serializers.CharField(max_length=500, allow_blank=True, required=False)
    font_family = serializers.ChoiceField(choices=("Gilroy", "Unbounded"), required=False)
    font_weight = serializers.ChoiceField(choices=(400, 500, 600, 700), required=False)
    font_size_pt = serializers.FloatField(min_value=6, max_value=96, required=False)
    align = serializers.ChoiceField(choices=("left", "center", "right"), required=False)
    shrink_to_fit = serializers.BooleanField(required=False)
    italic = serializers.BooleanField(required=False)
    uppercase = serializers.BooleanField(required=False)
    tracking_pt = serializers.FloatField(min_value=-1, max_value=8, required=False)
    line_height = serializers.FloatField(min_value=1, max_value=3, required=False)
    opacity = serializers.FloatField(min_value=0, max_value=1, required=False)
    resource_id = serializers.UUIDField(required=False)
    resource_slot = serializers.ChoiceField(choices=("logo", "selected_member_photo", "certificate_verification_qr",
                                                       "event_credential_qr"), required=False)
    colour_token = serializers.ChoiceField(choices=tuple(COLOURS), required=False)
    colour = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False,
                                    help_text="Free #RRGGBB text colour; overrides colour_token when set.")
    signature_slot = serializers.IntegerField(min_value=1, max_value=3, required=False,
                                              help_text="Signature layers: which signatory (1-3) this prints.")
    locked = serializers.BooleanField(required=False, help_text="Editor lock; the layer still prints.")
    hidden = serializers.BooleanField(required=False, help_text="Hidden layers are kept in the design but never print.")

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        for key in ("id", "resource_id"):
            if key in result:
                result[key] = str(result[key])
        return result
