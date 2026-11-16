"""Shapes for the badge desk, station and receipt routes (parity E-B2)."""
from django.utils.translation import gettext
from rest_framework import serializers

from apps.card_designs.serializers import EVENT_CARD_ROLES


class BadgeReceiptSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField(help_text="Unique per print; a retry or an offline sync never double-counts.")
    registration_id = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=("desk", "offline", "bulk"), required=False, default="desk",
                                     help_text="`bulk` for a browser print of many badges. The station route and the "
                                               "offline sync record `station` / `offline` themselves.")
    stock = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=EVENT_CARD_ROLES, required=False, allow_blank=True, default="")
    printed_at = serializers.DateTimeField(required=False)


class BadgeReceiptBatchSerializer(serializers.Serializer):
    receipts = BadgeReceiptSerializer(many=True, allow_empty=False)

    def validate_receipts(self, value):
        if len(value) > 200:
            raise serializers.ValidationError(gettext("At most 200 receipts may be reported at once."))
        return value


class BadgeReceiptResultSerializer(serializers.Serializer):
    recorded = serializers.IntegerField()
    duplicates = serializers.IntegerField(help_text="Receipts already recorded (or for another event) and skipped.")


class BadgeRowSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    card_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    team = serializers.CharField(allow_blank=True)
    crew_kind = serializers.CharField(allow_blank=True, help_text='Crew chip text such as "Volunteer · Door".')
    email = serializers.CharField(required=False, help_text="Present only when the published design prints the email.")
    answers = serializers.DictField(child=serializers.CharField(),
                                    help_text="`field:<key>` -> text, only the answers the design prints.")
    photo_card_id = serializers.IntegerField(allow_null=True, help_text="Card whose consented photo may be fetched.")
    photo = serializers.CharField(required=False, allow_null=True, help_text="Consented photo as a data URL (<= 200 KB), "
                                                                            "only on desk reads and only when the design shows a photo.")
    provisional = serializers.BooleanField(help_text="Waitlisted or pending: print without a verify QR.")
    status = serializers.CharField()
    checkin_payload = serializers.CharField(allow_null=True, help_text="Text for the check-in QR; null prints "
                                                                        "'Print at the desk'. Never rotated by a read.")


class BadgeDesignBundleSerializer(serializers.Serializer):
    designs = serializers.DictField(help_text="Design key -> {design_id, revision, stock, document, settings}.")
    roles = serializers.DictField(child=serializers.CharField(), help_text="Role -> design key.")
    logos = serializers.DictField(child=serializers.CharField(),
                                  help_text="space, event, organisation, sponsor_1..6 as PNG data URLs (<= 200 KB).")


class BadgeDeskSerializer(BadgeDesignBundleSerializer):
    event = serializers.DictField()
    server_time = serializers.DateTimeField()
    badge = BadgeRowSerializer(required=False, help_text="With `registration_id`.")
    badges = BadgeRowSerializer(many=True, required=False, help_text="With `status_set` (at most 500).")


class StationBadgeSerializer(BadgeDeskSerializer):
    pass
