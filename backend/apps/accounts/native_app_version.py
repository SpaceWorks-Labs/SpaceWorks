"""Minimum native app version, per platform (#128 C-6a).

``MIN_NATIVE_APP_VERSION_IOS`` and ``MIN_NATIVE_APP_VERSION_ANDROID`` are semver ``x.y.z``
compared numerically per platform; empty means no minimum. Device sign-in, the staff
step-up and every device refresh refuse an older app with HTTP 426 and the typed code
``native_app_update_required``. An app that sends no version, or a malformed one, counts
as older whenever a minimum is set: it predates the version contract.
"""

import re

from django.conf import settings
from rest_framework.exceptions import APIException

SEMVER = re.compile(r"\A(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\Z")
_SETTING = {"apple": "MIN_NATIVE_APP_VERSION_IOS", "android": "MIN_NATIVE_APP_VERSION_ANDROID"}


class NativeAppUpdateRequired(APIException):
    status_code = 426
    default_code = "native_app_update_required"
    default_detail = "This version of the app is no longer supported. Update the app to continue."

    def __init__(self, minimum):
        super().__init__({"detail": self.default_detail, "code": self.default_code,
                          "minimum_version": minimum})


def parse(value):
    match = SEMVER.match(value or "")
    return tuple(int(part) for part in match.groups()) if match else None


def minimum_for(platform):
    """The configured minimum for ``apple`` or ``android``, or "" for none."""
    name = _SETTING.get(platform)
    return getattr(settings, name, "") if name else ""


def assert_supported(platform, version):
    minimum = minimum_for(platform)
    if not minimum:
        return
    reported = parse(version) if isinstance(version, str) else None
    if reported is None or reported < parse(minimum):
        raise NativeAppUpdateRequired(minimum)
