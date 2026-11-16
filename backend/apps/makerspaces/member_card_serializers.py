from rest_framework import serializers

from apps.makerspaces.member_card_services import REISSUE_REASONS
from apps.makerspaces.models import MemberCard


class MemberCardSerializer(serializers.ModelSerializer):
    """Never carries the photo key or a URL that outlives the response."""

    membership_id = serializers.IntegerField(read_only=True, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)
    photo_set = serializers.SerializerMethodField()
    qr_active = serializers.SerializerMethodField()
    # Release 2 L3: the printed number (L4 pattern), valid-until, and open photo requests.
    number_display = serializers.SerializerMethodField()
    valid_until = serializers.SerializerMethodField()
    photo_request_open = serializers.SerializerMethodField()

    class Meta:
        model = MemberCard
        fields = (
            "id", "card_number", "number_display", "printed_name", "membership_id", "is_active", "photo_set",
            "photo_consent_at", "qr_active", "print_count", "last_printed_at", "issued_at", "valid_until",
            "photo_request_open", "last_emailed_at", "revoked_at", "revoked_reason", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_photo_set(self, obj) -> bool:
        return bool(obj.photo_object_key)

    def get_qr_active(self, obj) -> bool:
        return getattr(obj, "_qr_active", None) is not False and obj.is_active

    def get_number_display(self, obj) -> str:
        from apps.makerspaces.membership_number import display_number
        membership = obj.membership
        if membership is not None and membership.member_number:
            return display_number(membership)
        return str(obj.card_number)

    def get_valid_until(self, obj) -> str:
        from apps.card_designs.holders_member import fmt_date, term_state
        if obj.membership is None or not obj.is_active:
            return ""
        state, term = term_state(obj.membership)
        return fmt_date(term.ends_at) if term else ("No end date" if state == "open" else "Expired")

    def get_photo_request_open(self, obj) -> bool:
        from apps.card_designs.models import CardPhotoRequest
        return CardPhotoRequest.objects.filter(member_card=obj, resolved_at__isnull=True).exists()


class MemberCardIssueSerializer(serializers.Serializer):
    printed_name = serializers.CharField(max_length=200, required=False, allow_blank=True)


class MemberCardReissueSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=[(r, r) for r in REISSUE_REASONS])


class MemberCardRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=32, required=False, allow_blank=True)
    # Release 2 L3: staff must say why (stored encrypted on the card, never in audit meta).
    note = serializers.CharField(max_length=500, min_length=3)


class MemberCardOwnUpdateSerializer(serializers.Serializer):
    printed_name = serializers.CharField(max_length=200, allow_blank=True)


class MemberCardPhotoPresignSerializer(serializers.Serializer):
    content_type = serializers.CharField(max_length=64)


class MemberCardPhotoFinalizeSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=300)
    content_type = serializers.CharField(max_length=64)
    consent = serializers.BooleanField()


class MemberCardPrintSerializer(serializers.Serializer):
    card_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    preset = serializers.ChoiceField(choices=[("sheet", "sheet"), ("single", "single")], required=False, default="sheet")


class MemberCardResolveSerializer(serializers.Serializer):
    # A 32-hex desk payload, or (release 2 L3) a scanned check link / token.
    payload = serializers.CharField(max_length=300)


class MemberCardResolveResultSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=[("ok", "ok"), ("revoked", "revoked"), ("inactive", "inactive")])
    card_id = serializers.IntegerField(required=False)
    card_number = serializers.IntegerField(required=False)
    printed_name = serializers.CharField(required=False, allow_blank=True)
    membership_id = serializers.IntegerField(required=False)
    membership_status = serializers.CharField(required=False)
    photo_url = serializers.CharField(required=False, allow_null=True)


class MemberCardTemplateSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=False)
    page = serializers.CharField(required=False)
    orientation = serializers.CharField(required=False)
    card_width_mm = serializers.FloatField(required=False)
    card_height_mm = serializers.FloatField(required=False)
    margin_mm = serializers.FloatField(required=False)
    gap_mm = serializers.FloatField(required=False)
    front_fields = serializers.ListField(child=serializers.CharField(), required=False)
    back_text = serializers.CharField(required=False, allow_blank=True)
    include_photo = serializers.BooleanField(required=False)
    include_qr = serializers.BooleanField(required=False)
    name_font_size_pt = serializers.IntegerField(required=False)
    font_size_pt = serializers.IntegerField(required=False)
    crop_marks = serializers.BooleanField(required=False)
