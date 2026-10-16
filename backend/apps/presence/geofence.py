"""Server-authoritative, privacy-preserving presence geofence checks."""

from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt


ACCURACY_CEILING_M = 50
EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True)
class GeofenceResult:
    in_range: bool | None
    reason: str | None
    distance_m: float | None
    accuracy_m: float | None


def haversine_distance_m(latitude_a, longitude_a, latitude_b, longitude_b):
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    component = sin(latitude_delta / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(longitude_delta / 2) ** 2
    return EARTH_RADIUS_M * 2 * asin(sqrt(min(1, max(0, component))))


def evaluate_geofence(makerspace, *, latitude, longitude, accuracy):
    from apps.makerspaces.platform import feature_enabled

    if not feature_enabled(makerspace, "presence.geofence"):
        return None
    if not makerspace.geofence_effective:
        return None
    if latitude is None or longitude is None or accuracy is None:
        return GeofenceResult(in_range=None, reason="missing_coordinates", distance_m=None, accuracy_m=None)
    if not all(isfinite(value) for value in (latitude, longitude, accuracy)):
        return GeofenceResult(in_range=None, reason="missing_coordinates", distance_m=None, accuracy_m=None)
    distance_m = haversine_distance_m(float(makerspace.geofence_latitude), float(makerspace.geofence_longitude), latitude, longitude)
    if accuracy > ACCURACY_CEILING_M:
        return GeofenceResult(in_range=False, reason="low_accuracy", distance_m=distance_m, accuracy_m=accuracy)
    in_range = distance_m <= makerspace.geofence_radius_m
    return GeofenceResult(
        in_range=in_range,
        reason=None if in_range else "out_of_range",
        distance_m=distance_m,
        accuracy_m=accuracy,
    )


def require_inside(makerspace, *, latitude=None, longitude=None, accuracy=None):
    """Hard self-check-in rule. Validate then discard; GPS remains spoofable."""
    from .policy import PresenceError
    from apps.makerspaces.platform import feature_enabled

    if not feature_enabled(makerspace, "presence.geofence") or not makerspace.geofence_effective:
        raise PresenceError("geofence_unconfigured", "Self check-in needs a configured geofence. Ask staff to check you in.")
    if latitude is None or longitude is None:
        raise PresenceError("location_required", "Allow location access to check in, or ask staff to check you in.")
    values = (latitude, longitude) if accuracy is None else (latitude, longitude, accuracy)
    if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in values)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180
            or (accuracy is not None and accuracy < 0)):
        raise PresenceError("location_invalid", "Provide a valid location reading.")
    result = evaluate_geofence(makerspace, latitude=latitude, longitude=longitude, accuracy=accuracy or 0)
    if result is None or result.in_range is not True:
        code = "location_inaccurate" if result and result.reason == "low_accuracy" else "outside_geofence"
        raise PresenceError(code, "Location must be inside the makerspace radius. Ask staff for help.")


def geofence_metadata(result):
    if result is None:
        return {}
    metadata = {"geofence_checked": True, "in_range": result.in_range}
    if result.reason is not None:
        metadata["reason"] = result.reason
    if result.distance_m is not None:
        metadata["distance_bucket"] = _bucket(result.distance_m)
    if result.accuracy_m is not None:
        metadata["accuracy_bucket"] = _bucket(result.accuracy_m)
    return metadata


def _bucket(value):
    if value <= 10:
        return "0-10m"
    if value <= 25:
        return "11-25m"
    if value <= 50:
        return "26-50m"
    return "50m+"
