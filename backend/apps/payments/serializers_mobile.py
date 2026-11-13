from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers


class StripeMobilePaymentIntentResponseSerializer(serializers.Serializer):
    vendor = serializers.ChoiceField(choices=['stripe'])
    payment_id = serializers.IntegerField()
    client_secret = serializers.CharField()
    publishable_key = serializers.CharField()
    customer_id = serializers.CharField(required=False, allow_null=True)
    ephemeral_key = serializers.CharField(required=False, allow_null=True)


class RazorpayMobilePaymentIntentResponseSerializer(serializers.Serializer):
    vendor = serializers.ChoiceField(choices=['razorpay'])
    payment_id = serializers.IntegerField()
    key_id = serializers.CharField()
    order_id = serializers.CharField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()


MobilePaymentIntentResponseSerializer = PolymorphicProxySerializer(
    component_name='MobilePaymentIntentResponse',
    serializers={
        'stripe': StripeMobilePaymentIntentResponseSerializer,
        'razorpay': RazorpayMobilePaymentIntentResponseSerializer,
    },
    resource_type_field_name='vendor',
)
