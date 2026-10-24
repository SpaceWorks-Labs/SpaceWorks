from rest_framework import serializers
from apps.events.serializers_staff_tools import MemberEventTicketSerializer, TicketPublicFieldsSerializer


class TicketEventSerializer(TicketPublicFieldsSerializer):
    id = serializers.IntegerField(read_only=True)


class ProgrammeTicketSerializer(MemberEventTicketSerializer):
    event = TicketEventSerializer(read_only=True)
    attended_at = serializers.DateTimeField(allow_null=True, read_only=True)
    credential_mode = serializers.ChoiceField(choices=("legacy", "v2", "inert"), read_only=True)
