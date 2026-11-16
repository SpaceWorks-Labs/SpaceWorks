from django.utils.translation import gettext
from collections.abc import Mapping

from rest_framework import serializers


class EventWebsitePublishInput(serializers.Serializer):
    publish_website = serializers.BooleanField(default=False)
    website_revision = serializers.IntegerField(min_value=1, required=False)
    publish_without_room = serializers.BooleanField(
        default=False, help_text="Decision 223 (g): publish although the linked room booking was rejected, "
        "cancelled or is missing. Audited as `event.published_without_room`; no venue fee is charged.")

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, Mapping) else set()
        if unknown:
            # Field-keyed: a bare list from a top-level to_internal_value breaks .errors.
            raise serializers.ValidationError({key: ["Unknown publication field."] for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, data):
        if data["publish_website"] and "website_revision" not in data:
            raise serializers.ValidationError({"website_revision": gettext("Reload the saved website before publishing.")})
        return data
