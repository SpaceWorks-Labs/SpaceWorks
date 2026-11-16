from rest_framework import serializers
from apps.events.serializers_staff_tools import MemberEventTicketSerializer, TicketPublicFieldsSerializer


class TicketEventSerializer(TicketPublicFieldsSerializer):
    id = serializers.IntegerField(read_only=True)


class ProgrammeTicketSerializer(MemberEventTicketSerializer):
    event = TicketEventSerializer(read_only=True)
    attended_at = serializers.DateTimeField(allow_null=True, read_only=True)
    credential_mode = serializers.ChoiceField(choices=("legacy", "v2", "inert"), read_only=True)
    # L1 (G3, X1): released by `online_delivery` -- the join link to confirmed registrants
    # of an online/hybrid event only, the venue map link for in-person and hybrid events.
    delivery_mode = serializers.ChoiceField(choices=("in_person", "online", "hybrid"), allow_null=True,
                                            read_only=True)
    join_url = serializers.URLField(allow_null=True, read_only=True)
    map_url = serializers.URLField(allow_null=True, read_only=True)
    # Parity E-B5/E-F3: pay by this time or the place is released (null without an open pay window).
    pay_by = serializers.DateTimeField(allow_null=True, read_only=True)
