from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers

from apps.payments.credential_validation import (
    update_payment_settings,
    update_platform_payment_settings,
    validate_makerspace_credential_changes,
)
from apps.payments.models import (
    MakerspacePaymentSettings,
    PlatformStripeConnectSettings,
    currency_validator,
)
from apps.payments.resolution import resolve_payment_source


class MakerspacePaymentSettingsSerializer(serializers.ModelSerializer):
    default_currency = serializers.CharField(required=False, max_length=3)
    stripe_publishable_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )
    stripe_secret_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    stripe_webhook_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    stripe_secret_key_set = serializers.SerializerMethodField()
    stripe_webhook_secret_set = serializers.SerializerMethodField()
    stripe_publishable_key_set = serializers.SerializerMethodField()
    razorpay_key_id = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )
    razorpay_key_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255,
        trim_whitespace=False,
    )
    razorpay_webhook_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255,
        trim_whitespace=False,
    )
    razorpay_key_id_set = serializers.SerializerMethodField()
    razorpay_key_secret_set = serializers.SerializerMethodField()
    razorpay_webhook_secret_set = serializers.SerializerMethodField()
    stripe_webhook_url = serializers.SerializerMethodField()
    razorpay_webhook_url = serializers.SerializerMethodField()
    effective_mode = serializers.SerializerMethodField()

    class Meta:
        model = MakerspacePaymentSettings
        fields = (
            "provider",
            "razorpay_key_id", "razorpay_key_id_set",
            "razorpay_key_secret", "razorpay_key_secret_set",
            "razorpay_webhook_secret", "razorpay_webhook_secret_set",
            "stripe_webhook_url", "razorpay_webhook_url",
            "default_currency",
            "stripe_publishable_key",
            "stripe_publishable_key_set",
            "stripe_secret_key",
            "stripe_secret_key_set",
            "stripe_webhook_secret",
            "stripe_webhook_secret_set",
            "connect_account_id",
            "connect_status",
            "connect_charges_enabled",
            "connect_payouts_enabled",
            "connect_status_updated_at",
            "effective_mode",
            "loan_deposit_mode",
            "loan_deposit_amount",
            "loan_late_fee_per_day",
            "loan_late_fee_cap",
            "loan_grace_days",
            "loan_deposit_blocks_issue",
        )
        read_only_fields = (
            "connect_account_id",
            "connect_status",
            "connect_charges_enabled",
            "connect_payouts_enabled",
            "connect_status_updated_at",
            "effective_mode",
        )

    def get_stripe_secret_key_set(self, obj) -> bool:
        return obj.stripe_secret_key_set

    def get_stripe_publishable_key_set(self, obj) -> bool:
        return obj.stripe_publishable_key_set

    def get_stripe_webhook_secret_set(self, obj) -> bool:
        return obj.stripe_webhook_secret_set

    def get_razorpay_key_id_set(self, obj) -> bool:
        return bool(obj.razorpay_key_id)

    def get_razorpay_key_secret_set(self, obj) -> bool:
        return obj.razorpay_key_secret_set

    def get_razorpay_webhook_secret_set(self, obj) -> bool:
        return obj.razorpay_webhook_secret_set

    def _webhook_url(self, obj, provider):
        path = reverse(f"{provider}-webhook", kwargs={"public_code": obj.makerspace.public_code})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_stripe_webhook_url(self, obj) -> str:
        return self._webhook_url(obj, "stripe")

    def get_razorpay_webhook_url(self, obj) -> str:
        return self._webhook_url(obj, "razorpay")

    def get_effective_mode(self, obj) -> str:
        source = resolve_payment_source(obj.makerspace)
        return source.provider if source else "unavailable"

    def validate_default_currency(self, value):
        normalized = value.strip().lower()
        try:
            currency_validator(normalized)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return normalized

    def validate(self, attrs):
        try:
            validate_makerspace_credential_changes(self.instance, attrs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs

    def update(self, instance, validated_data):
        try:
            return update_payment_settings(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class PaymentSettingsErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)


class PaymentProviderConflictSerializer(PaymentSettingsErrorSerializer):
    code = serializers.ChoiceField(choices=["payment_provider_conflict"])


class StripeConnectOnboardingSerializer(serializers.Serializer):
    authorize_url = serializers.URLField()


class PlatformStripeConnectSettingsSerializer(serializers.ModelSerializer):
    stripe_publishable_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )
    stripe_secret_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    stripe_webhook_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    stripe_secret_key_set = serializers.SerializerMethodField()
    stripe_webhook_secret_set = serializers.SerializerMethodField()
    stripe_publishable_key_set = serializers.SerializerMethodField()

    class Meta:
        model = PlatformStripeConnectSettings
        fields = (
            "id",
            "stripe_publishable_key",
            "stripe_publishable_key_set",
            "stripe_secret_key",
            "stripe_secret_key_set",
            "stripe_webhook_secret",
            "stripe_webhook_secret_set",
            "stripe_connect_client_id",
            "application_fee_bps",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "stripe_publishable_key_set",
            "stripe_secret_key_set",
            "stripe_webhook_secret_set",
            "updated_at",
        )

    def get_stripe_secret_key_set(self, obj) -> bool:
        return bool(obj.stripe_secret_key)

    def get_stripe_publishable_key_set(self, obj) -> bool:
        return obj.stripe_publishable_key_set

    def get_stripe_webhook_secret_set(self, obj) -> bool:
        return bool(obj.stripe_webhook_secret)

    def update(self, instance, validated_data):
        try:
            return update_platform_payment_settings(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
