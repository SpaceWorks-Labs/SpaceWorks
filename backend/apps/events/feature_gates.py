"""Event feature guards without dependencies on event models or workflows."""

from apps.makerspaces.guards import feature_off

from apps.makerspaces.platform import feature_enabled


def require_feature(event, key):
    if not feature_enabled(event.makerspace, key):
        raise feature_off(key, "This events feature is turned off.")
