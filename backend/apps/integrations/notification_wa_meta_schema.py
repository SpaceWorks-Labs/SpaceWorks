"""OpenAPI-only webhook shapes; runtime parsing always follows raw HMAC validation."""
from rest_framework import serializers


class MetaMetadataSerializer(serializers.Serializer):
    phone_number_id = serializers.CharField()


class MetaProviderErrorSerializer(serializers.Serializer):
    code = serializers.IntegerField()


class MetaStatusSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.ChoiceField(choices=["sent", "delivered", "read", "failed"])
    recipient_id = serializers.CharField(required=False)
    timestamp = serializers.CharField(required=False)
    errors = MetaProviderErrorSerializer(many=True, required=False)


class MetaMessageSerializer(serializers.Serializer):
    id = serializers.CharField()
    from_ = serializers.CharField(source="from")
    timestamp = serializers.CharField()
    type = serializers.CharField()
    text = serializers.DictField(child=serializers.CharField(), required=False)
    button = serializers.DictField(child=serializers.CharField(), required=False)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        fields["from"].source = None
        return fields


class MetaUserPreferenceSerializer(serializers.Serializer):
    wa_id = serializers.CharField()
    category = serializers.CharField()
    value = serializers.CharField()
    timestamp = serializers.CharField(required=False)


class MetaValueSerializer(serializers.Serializer):
    messaging_product = serializers.ChoiceField(choices=["whatsapp"])
    metadata = MetaMetadataSerializer()
    messages = MetaMessageSerializer(many=True, required=False)
    statuses = MetaStatusSerializer(many=True, required=False)
    user_preferences = MetaUserPreferenceSerializer(many=True, required=False)


class MetaChangeSerializer(serializers.Serializer):
    field = serializers.ChoiceField(choices=["messages", "user_preferences"])
    value = MetaValueSerializer()


class MetaEntrySerializer(serializers.Serializer):
    id = serializers.CharField(help_text="Configured WhatsApp Business Account ID.")
    changes = MetaChangeSerializer(many=True)


class MetaWebhookSerializer(serializers.Serializer):
    object = serializers.ChoiceField(choices=["whatsapp_business_account"])
    entry = MetaEntrySerializer(many=True)
