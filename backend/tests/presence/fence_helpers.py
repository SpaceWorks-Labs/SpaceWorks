"""Self check-in is HARD-geofenced (v2 §D): configure a fence and check in at its centre."""
INSIDE = {"latitude": 0, "longitude": 0, "accuracy": 5}


def fence(space, radius_m=100):
    space.geofence_enabled = True
    space.geofence_latitude = 0
    space.geofence_longitude = 0
    space.geofence_radius_m = radius_m
    space.enabled_features = sorted(set(space.enabled_features or []) | {"presence.geofence"})
    space.save(update_fields=["geofence_enabled", "geofence_latitude", "geofence_longitude",
                              "geofence_radius_m", "enabled_features"])
    return space
