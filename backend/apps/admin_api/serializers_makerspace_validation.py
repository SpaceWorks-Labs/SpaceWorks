from django.utils.translation import gettext
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.inventory import public_image_storage
from apps.integrations.smtp_validation import validate_smtp_settings
from apps.integrations.webhook_validation import validate_webhook_url
from apps.makerspaces import domain_verification, limits
from apps.makerspaces.capabilities import prune_features, validate_capabilities
from apps.makerspaces.platform import available_modules
from apps.makerspaces.theme_validation import validate_theme_config
from apps.makerspaces.validators import (
    validate_google_maps_url,
    validate_presence_presets,
)
from apps.separability.tombstones import unavailable_apps
from apps.admin_api.serializers_makerspace_domain import validate_frontend_domain


class MakerspaceValidationMixin:
    def get_unavailable_apps(self, obj) -> list[str]:
        return unavailable_apps()

    def get_enabled_modules(self, obj) -> list[str]:
        return available_modules(obj)

    def get_telegram_bot_token_set(self, obj) -> bool:
        return bool(obj.telegram_bot_token)

    def get_smtp_password_set(self, obj) -> bool:
        return bool(obj.smtp_password)

    def get_slack_webhook_url_set(self, obj) -> bool:
        return bool(obj.slack_webhook_url)

    def get_mattermost_webhook_url_set(self, obj) -> bool:
        return bool(obj.mattermost_webhook_url)

    def get_discord_webhook_url_set(self, obj) -> bool:
        return bool(obj.discord_webhook_url)

    def validate_slack_webhook_url(self, value):
        return validate_webhook_url(value)

    def validate_mattermost_webhook_url(self, value):
        return validate_webhook_url(value)

    def validate_discord_webhook_url(self, value):
        return validate_webhook_url(value)

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_logo_url(self, obj):
        return public_image_storage.public_url(obj.logo_key) or None

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_cover_image_url(self, obj):
        return public_image_storage.public_url(obj.cover_image_key) or None

    @extend_schema_field(
        {
            "type": "object",
            "nullable": True,
            "properties": {
                "host": {"type": "string"},
                "type": {"type": "string"},
                "value": {"type": "string"},
            },
        }
    )
    def get_domain_verification_record(self, obj):
        return domain_verification.expected_record(obj)

    @extend_schema_field({"type": "integer", "description": "People whose only second factor is a passkey on "
                          "this custom domain: a domain change ends their passkey sign-in there."})
    def get_passkey_only_accounts(self, obj) -> int:
        return domain_verification.passkey_only_accounts(obj)

    @extend_schema_field({"type": "boolean"})
    def get_platform_hosting(self, obj) -> bool:
        return not domain_verification.is_self_host()

    @extend_schema_field({"type": "boolean"})
    def get_is_platform_subdomain(self, obj) -> bool:
        return (
            bool(obj.frontend_domain)
            and domain_verification._is_platform_managed(obj.frontend_domain)
            and obj.frontend_domain_status == obj.DomainStatus.VERIFIED
        )

    def validate_theme_config(self, value):
        try:
            return validate_theme_config(value)
        except DjangoValidationError as exc:
            if any(error.code == "theme_contrast" for error in exc.error_list):
                raise serializers.ValidationError({
                    "code": "theme_contrast", "messages": exc.messages,
                }) from exc
            raise serializers.ValidationError(exc.messages) from exc

    def validate_public_code(self, value):
        return value.upper()

    def validate_map_url(self, value):
        validate_google_maps_url(value)
        return value

    def validate_default_loan_days(self, value):
        if value < 1:
            raise serializers.ValidationError(gettext("Default loan days must be at least 1."))
        return value

    def validate_filament_low_stock_threshold_grams(self, value):
        if value < 0:
            raise serializers.ValidationError(
                gettext("Filament low-stock threshold cannot be negative.")
            )
        return value

    def validate_presence_preset_minutes(self, value):
        try:
            return validate_presence_presets(value)
        except Exception as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def to_internal_value(self, data):
        request = self.context.get("request")
        if request is not None and "enabled_modules" in data:
            raise PermissionDenied(gettext("Capabilities can only be changed in /control/."))
        return super().to_internal_value(data)

    def validate(self, attrs):
        geofence_enabled = attrs.get(
            "geofence_enabled",
            self.instance.geofence_enabled if self.instance else False,
        )
        latitude = attrs.get(
            "geofence_latitude",
            self.instance.geofence_latitude if self.instance else None,
        )
        longitude = attrs.get(
            "geofence_longitude",
            self.instance.geofence_longitude if self.instance else None,
        )
        if geofence_enabled and (latitude is None or longitude is None):
            raise serializers.ValidationError(
                {
                    "geofence_enabled": (
                        gettext("Set both latitude and longitude before enabling the geofence.")
                    )
                }
            )

        effective_modules = attrs.get(
            "enabled_modules", self.instance.enabled_modules if self.instance else []
        )
        effective_features = attrs.get(
            "enabled_features", self.instance.enabled_features if self.instance else []
        )
        if "enabled_features" not in attrs:
            effective_features, _dropped = prune_features(
                effective_features, effective_modules
            )
        try:
            _, enabled_features = validate_capabilities(
                effective_modules,
                effective_features,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        if "enabled_features" in attrs:
            attrs["enabled_features"] = enabled_features
        if "resource_limit_overrides" in attrs:
            actor = self.context["request"].user
            is_superadmin = actor.is_superuser or actor.role == User.Role.SUPERADMIN
            if not is_superadmin:
                raise serializers.ValidationError(
                    {
                        "resource_limit_overrides": (
                            gettext("Only a superadmin can set per-space resource limits.")
                        )
                    }
                )
            attrs["resource_limit_overrides"] = (
                limits.validate_resource_limit_overrides(
                    attrs["resource_limit_overrides"]
                )
            )

        if "frontend_domain" in attrs:
            # #192: directory visibility no longer depends on a domain; clearing the
            # domain leaves "hide from the platform" exactly as the Space Manager set it.
            self._validate_frontend_domain(attrs)
        from apps.integrations.email_provider_serializers import validate_provider_update
        validate_provider_update(attrs, self.instance, tenant=True)
        return attrs

    def _validate_frontend_domain(self, attrs):
        validate_frontend_domain(self, attrs)
