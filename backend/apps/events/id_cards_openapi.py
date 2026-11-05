"""Typed shapes for the organiser event-card routes (#193 OpenAPI contract): documentation only."""
from rest_framework import serializers


class IssueResultSerializer(serializers.Serializer):
    issued = serializers.IntegerField()
    revoked = serializers.IntegerField()


class CardRoleRequestSerializer(serializers.Serializer):
    role = serializers.CharField(help_text="attendee, speaker, mentor, judge, volunteer or crew.")


class CardScanRequestSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=300, help_text="The scanned QR text.")
    check_in = serializers.BooleanField(required=False, help_text="Check in when exactly one registration matches.")


class CardScanRowSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    confirmable = serializers.BooleanField()


class CardScanResultSerializer(serializers.Serializer):
    checked_in = serializers.IntegerField(allow_null=True, help_text="The registration checked in, if any.")
    registrations = CardScanRowSerializer(many=True)


class EventCardSettingsSerializer(serializers.Serializer):
    extras_visible_to_organizers = serializers.BooleanField()
    design_approval_required = serializers.BooleanField(allow_null=True)
    design_approval_inherited = serializers.BooleanField(allow_null=True)


class EventCardSettingsRequestSerializer(serializers.Serializer):
    extras_visible_to_organizers = serializers.BooleanField(required=False)
    design_approval_required = serializers.BooleanField(required=False, allow_null=True,
                                                         help_text="null follows the organisation, then the space.")


class CardExtrasRowSerializer(serializers.Serializer):
    card_id = serializers.IntegerField()
    name = serializers.CharField()
    blood_group = serializers.CharField(allow_blank=True)
    emergency_contact_name = serializers.CharField(allow_blank=True)
    emergency_contact_phone = serializers.CharField(allow_blank=True)
