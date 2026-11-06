"""The L4 membership switches as API gates (#95: off means no surface, 404).

`require_membership_feature` answers 404 when the `membership` module or the named
capability is off for the space, so a switched-off feature has no API surface and does
not reveal that it exists. `require_membership_feature_locked` re-checks both under the
makerspace row lock for writers (the same reason `require_module_locked` exists).
"""
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.makerspaces.platform import feature_enabled, module_enabled


def membership_feature_on(makerspace, key):
    return module_enabled(makerspace, "membership") and feature_enabled(makerspace, f"membership.{key}")


def require_membership_feature(makerspace, key):
    if not membership_feature_on(makerspace, key):
        raise NotFound(gettext("This feature is not available here."))
    return makerspace


def require_membership_feature_locked(makerspace_or_id, key):
    from apps.makerspaces.guards import SurfaceOff, require_module_locked

    try:
        locked = require_module_locked(makerspace_or_id, "membership")
    except SurfaceOff as exc:  # the module went off while we waited for the lock
        raise NotFound(gettext("This feature is not available here.")) from exc
    if not feature_enabled(locked, f"membership.{key}"):
        raise NotFound(gettext("This feature is not available here."))
    return locked
