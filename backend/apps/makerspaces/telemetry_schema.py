"""Public-only telemetry configuration. No provider credentials belong here."""
import re
import math
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework import serializers
from django.utils.translation import gettext


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({key: "Unknown field." for key in set(data) - set(self.fields)})
        return super().to_internal_value(data)


def approved_url(value, *, origin_only=True):
    if not value:
        return value
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        origin = f"https://{host}" + (f":{parsed.port}" if parsed.port else "")
        allowed = getattr(settings, "WEB_TELEMETRY_ALLOWED_ORIGINS", ())
        # urlsplit silently drops tab/newline and tolerates "?"/"#" with empty parts; any of those
        # (or whitespace/backslashes) would make the stored string differ from what was checked.
        if (value != value.strip() or re.search(r"[\s\\]", value) or "?" in value or "#" in value
                or parsed.scheme != "https" or not parsed.hostname or (origin_only and parsed.username) or parsed.password
                or parsed.query or parsed.fragment or (origin_only and parsed.path not in ("", "/"))
                or origin not in allowed):
            raise ValueError
    except ValueError:
        raise serializers.ValidationError(gettext("HTTPS origin must be explicitly operator-approved; no credentials, query or fragment."))
    # Store the canonical origin that was checked, never the raw input.
    return origin if origin_only else value.rstrip("/")


class ProviderSerializer(StrictSerializer):
    provider = serializers.ChoiceField(choices=("none", "plausible", "umami", "ga4", "firebase", "posthog"))
    site_id = serializers.RegexField(r"^[A-Za-z0-9._:-]*$", max_length=128, allow_blank=True)
    endpoint = serializers.CharField(max_length=300, allow_blank=True, trim_whitespace=False)

    def validate_endpoint(self, value):
        return approved_url(value)

    def validate(self, value):
        provider, site = value["provider"], value["site_id"]
        if provider not in ("none", "firebase") and not site:
            raise serializers.ValidationError({"site_id": gettext("A selected provider needs an identifier.")})
        if provider == "firebase" and site:
            raise serializers.ValidationError({"site_id": gettext("For Firebase use firebase.measurement_id only.")})
        if provider == "umami" and not value["endpoint"]:
            raise serializers.ValidationError({"endpoint": gettext("Umami requires an approved origin.")})
        if provider == "ga4" and not re.fullmatch(r"G-[A-Z0-9]+", site):
            raise serializers.ValidationError({"site_id": gettext("Use a GA4 measurement ID.")})
        patterns = {
            "umami": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "posthog": r"phc_[A-Za-z0-9]+", "clarity": r"[A-Za-z0-9]+",
            "plausible": r"[A-Za-z0-9.-]+",
        }
        if provider in patterns and not re.fullmatch(patterns[provider], site):
            raise serializers.ValidationError({"site_id": gettext("Invalid identifier for this provider.")})
        return value


class ReplaySerializer(ProviderSerializer):
    provider = serializers.ChoiceField(choices=("none", "clarity", "posthog"))


class SentrySerializer(StrictSerializer):
    enabled = serializers.BooleanField()
    dsn = serializers.CharField(max_length=500, allow_blank=True, trim_whitespace=False)
    sample_rate = serializers.FloatField(min_value=0, max_value=1)

    def validate_dsn(self, value):
        value = approved_url(value, origin_only=False)
        if value:
            parsed = urlsplit(value)
            if (not re.fullmatch(r"[A-Za-z0-9]+", parsed.username or "")
                    or not re.fullmatch(r"/\d+", parsed.path)):
                raise serializers.ValidationError(gettext("Sentry DSN needs a public ingest key and numeric project path."))
        return value

    def validate_sample_rate(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError(gettext("Sample rate must be finite."))
        return value

    def validate(self, value):
        if value["enabled"] and not value["dsn"]:
            raise serializers.ValidationError({"dsn": gettext("Required when enabled.")})
        return value


class PerformanceSerializer(StrictSerializer):
    enabled = serializers.BooleanField()
    sample_rate = serializers.FloatField(min_value=0, max_value=1)

    def validate_sample_rate(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError(gettext("Sample rate must be finite."))
        return value


class DiagnosticsSerializer(StrictSerializer):
    sentry = SentrySerializer()
    firebase_performance = PerformanceSerializer()


class FirebaseSerializer(StrictSerializer):
    api_key = serializers.RegexField(r"^[A-Za-z0-9_-]*$", max_length=128, allow_blank=True)
    auth_domain = serializers.RegexField(r"^[A-Za-z0-9.-]*$", max_length=253, allow_blank=True)
    project_id = serializers.RegexField(r"^[a-z0-9-]*$", max_length=63, allow_blank=True)
    app_id = serializers.RegexField(r"^[A-Za-z0-9:_-]*$", max_length=128, allow_blank=True)
    messaging_sender_id = serializers.RegexField(r"^[0-9]*$", max_length=32, allow_blank=True)
    measurement_id = serializers.RegexField(r"^(G-[A-Z0-9]+)?$", max_length=32, allow_blank=True)
    vapid_public_key = serializers.RegexField(r"^[A-Za-z0-9_-]*$", max_length=256, allow_blank=True)


class TelemetryConfigSerializer(StrictSerializer):
    pageview = ProviderSerializer()
    replay = ReplaySerializer()
    diagnostics = DiagnosticsSerializer()
    firebase = FirebaseSerializer()

    def validate(self, value):
        firebase = value["firebase"]
        if value["pageview"]["provider"] == "firebase" and not firebase["measurement_id"]:
            raise serializers.ValidationError({"firebase": {"measurement_id": gettext("Required for Firebase Analytics.")}})
        page, replay = value["pageview"], value["replay"]
        if page["provider"] == replay["provider"] == "posthog" and (
                page["site_id"] != replay["site_id"] or
                (page["endpoint"] or "https://us.i.posthog.com") != (replay["endpoint"] or "https://us.i.posthog.com")):
            raise serializers.ValidationError({"replay": gettext("PostHog analytics and replay must use the same project and origin.")})
        if value["pageview"]["provider"] == "firebase" or value["diagnostics"]["firebase_performance"]["enabled"]:
            if not all(firebase[key] for key in ("api_key", "project_id", "app_id")):
                raise serializers.ValidationError({"firebase": gettext("api_key, project_id and app_id are required.")})
        return value


class TelemetryEnvelopeSerializer(StrictSerializer):
    config = TelemetryConfigSerializer()
