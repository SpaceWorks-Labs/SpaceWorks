"""Request body for the account's own language preference (phase 8 i18n)."""

from rest_framework import serializers

from config.locale_registry import django_languages


class PreferredLocaleUpdateSerializer(serializers.Serializer):
    """Exactly ``{"preferred_locale": "<code>"}`` or ``{"preferred_locale": null}``.

    Null means "use the makerspace default". Blank strings and unsupported codes are 400s;
    there is no user id: only the signed-in account's own preference can change.
    """

    preferred_locale = serializers.ChoiceField(
        choices=django_languages(), allow_null=True, allow_blank=False,
        help_text="A supported locale code, or null to follow the makerspace default.",
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - {"preferred_locale"}:
            raise serializers.ValidationError({"non_field_errors": [
                serializers.ErrorDetail("Only preferred_locale may be changed here.", code="unexpected_field"),
            ]})
        return super().to_internal_value(data)
