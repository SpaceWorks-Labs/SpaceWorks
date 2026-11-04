from collections.abc import Mapping

from rest_framework import serializers


class EventWebsitePublishInput(serializers.Serializer):
    publish_website = serializers.BooleanField(default=False)
    website_revision = serializers.IntegerField(min_value=1, required=False)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, Mapping) else set()
        if unknown:
            # Field-keyed: a bare list from a top-level to_internal_value breaks .errors.
            raise serializers.ValidationError({key: ["Unknown publication field."] for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, data):
        if data["publish_website"] and "website_revision" not in data:
            raise serializers.ValidationError({"website_revision": "Reload the saved website before publishing."})
        return data
