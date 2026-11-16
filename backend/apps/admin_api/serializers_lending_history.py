from rest_framework import serializers


class LendingHistoryActorSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()


class LendingHistoryEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    request_id = serializers.IntegerField(help_text="Decision 242: links the row to its request.")
    requester_id = serializers.IntegerField(allow_null=True, help_text="The borrower's account, when there is one.")
    username = serializers.CharField()
    issued_at = serializers.DateTimeField()
    quantity = serializers.IntegerField()
    issued_by = LendingHistoryActorSerializer(allow_null=True)
    accepted_by = LendingHistoryActorSerializer(allow_null=True)


class LendingHistoryResponseSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    last_borrower = LendingHistoryEntrySerializer(allow_null=True)
    recent = LendingHistoryEntrySerializer(many=True)
    count = serializers.IntegerField(help_text="All lends of this item, for paging.")
