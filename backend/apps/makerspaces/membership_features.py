"""The L4 membership switches as API gates (#95: off means no surface, 404).

`require_membership_feature` answers 404 when the `membership` module or the named
capability is off for the space, so a switched-off feature has no API surface.
`require_membership_feature_locked` re-checks both under the makerspace row lock for
writers (the same reason `require_module_locked` exists). The 404 is the typed
`SurfaceOff` body every other switch answers with (#183B: the body names the switch).
"""
from apps.makerspaces.platform import feature_enabled, module_enabled


def membership_feature_on(makerspace, key):
    return module_enabled(makerspace, "membership") and feature_enabled(makerspace, f"membership.{key}")


def _off(makerspace, key):
    from apps.makerspaces.guards import feature_off, module_off

    if not module_enabled(makerspace, "membership"):
        return module_off("membership")
    return feature_off(f"membership.{key}")


def require_membership_feature(makerspace, key):
    if not membership_feature_on(makerspace, key):
        raise _off(makerspace, key)
    return makerspace


def require_membership_feature_locked(makerspace_or_id, key):
    from apps.makerspaces.guards import SurfaceOff, feature_off, module_off, require_module_locked

    try:
        locked = require_module_locked(makerspace_or_id, "membership")
    except SurfaceOff as exc:  # the module went off while we waited for the lock
        raise module_off("membership") from exc
    if not feature_enabled(locked, f"membership.{key}"):
        raise feature_off(f"membership.{key}")
    return locked
