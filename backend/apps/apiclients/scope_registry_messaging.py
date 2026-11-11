"""Explicit denies: messaging is a user-session/provider-signature surface."""
ROUTE_METHODS = {
    "auth-browser-state": ("GET", "HEAD"),
    "admin-platform-firebase-web-settings": ("GET", "HEAD", "PATCH"),
    "member-messaging": ("GET", "HEAD"),
    "member-messaging-consent": ("POST",),
    "messaging-settings": ("GET", "HEAD", "PATCH"),
    "messaging-test": ("POST",),
    "whatsapp-template-list": ("GET", "HEAD", "POST"),
    "whatsapp-template-detail": ("PATCH", "DELETE"),
    "whatsapp-template-catalog": ("GET", "HEAD"),
    "messaging-twilio-platform-status": ("POST",),
    "messaging-twilio-platform-inbound": ("POST",),
    "messaging-twilio-status": ("POST",),
    "messaging-twilio-inbound": ("POST",),
    "messaging-meta-platform": ("GET", "HEAD", "POST"),
    "messaging-meta": ("GET", "HEAD", "POST"),
}
from apps.separability.tombstones import tombstoned_app_labels
if "analytics" not in tombstoned_app_labels():
    ROUTE_METHODS.update({
        "admin-makerspace-telemetry": ("GET", "HEAD", "PATCH"),
        "admin-platform-telemetry": ("GET", "HEAD", "PATCH"),
    })
if "notifications" not in tombstoned_app_labels():
    ROUTE_METHODS.update({
        "notifications:browser-firebase-challenge": ("POST", "DELETE"),
        "notifications:browser-firebase-confirm": ("POST",),
        "notifications:browser-firebase-config": ("GET", "HEAD"),
        "notifications:browser-firebase-may-resume": ("POST",),
        "notifications:browser-firebase-global-may-resume": ("POST",),
    })
if "events" not in tombstoned_app_labels():
    ROUTE_METHODS["admin-event-booking-link"] = ("GET", "HEAD", "POST")
    ROUTE_METHODS["admin-event-booking-replacement"] = ("POST",)
    ROUTE_METHODS["admin-event-venue"] = ("GET", "HEAD")  # decision 223 G6: read-only venue panel
    ROUTE_METHODS["admin-event-create-with-room"] = ("POST",)  # decision 223 G6: event + room step
    ROUTE_METHODS["admin-event-room-choices"] = ("GET", "HEAD")  # 0.12.0: organizer room choice list
    ROUTE_METHODS["admin-event-registration-queue"] = ("GET", "HEAD")  # open items A22: cross-event queue
    ROUTE_METHODS["admin-event-workshop-machines"] = ("GET", "HEAD", "POST")
    ROUTE_METHODS["admin-event-workshop-machine-replacement"] = ("POST",)
    ROUTE_METHODS["admin-event-workshop-machine-link"] = ("DELETE",)
    ROUTE_METHODS.update({"admin-request-event-context": ("GET", "HEAD", "PUT", "DELETE"),
                          "admin-direct-loan-event-context": ("GET", "HEAD", "PUT", "DELETE")})
if "bookings" not in tombstoned_app_labels():
    ROUTE_METHODS.update({"admin-request-booking-context": ("GET", "HEAD", "PUT", "DELETE"),
                          "admin-direct-loan-booking-context": ("GET", "HEAD", "PUT", "DELETE")})
DENIED_KEYS = frozenset((name, method) for name, methods in ROUTE_METHODS.items() for method in methods)


def definitions():
    return tuple((name, methods, frozenset(), "global", False, False) for name, methods in ROUTE_METHODS.items())
