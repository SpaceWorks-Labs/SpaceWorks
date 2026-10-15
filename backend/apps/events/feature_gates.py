"""Event feature guards without dependencies on event models or workflows."""

from rest_framework.exceptions import ValidationError

from apps.makerspaces.platform import feature_enabled


def require_feature(event, key):
    if not feature_enabled(event.makerspace, key):
        raise ValidationError({"detail": "This events feature is disabled."})
