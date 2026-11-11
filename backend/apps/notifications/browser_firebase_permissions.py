"""Browser Firebase push is a web-session surface: a native device grant may not reuse it.

Native apps register push through `/push/devices/` (APNs/FCM bound to the device grant);
an FID proven here belongs to a browser installation, so a native token is refused (403).
"""
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated


def is_native_device_request(request):
    if getattr(request, "device_grant", None) is not None:
        return True
    auth = getattr(request, "auth", None)
    return bool(auth is not None and hasattr(auth, "get") and auth.get("device_grant_id"))


class IsBrowserSession(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if is_native_device_request(request):
            raise PermissionDenied(gettext("Browser push is not available to native device sessions."))
        return True
