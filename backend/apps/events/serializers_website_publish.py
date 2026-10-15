from collections.abc import Mapping

from rest_framework import serializers


class EventWebsitePublishInput(serializers.Serializer):
    publish_website = serializers.BooleanField(default=False)
    website_revision = serializers.IntegerField(min_value=1, required=False)

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise serializers.ValidationError("Unknown publication fields.")
        return super().to_internal_value(data)

    def validate(self, data):
        if data["publish_website"] and "website_revision" not in data:
            raise serializers.ValidationError({"website_revision": "Reload the saved website before publishing."})
        return data
