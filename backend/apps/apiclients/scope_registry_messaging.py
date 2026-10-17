"""Explicit denies: messaging is a user-session/provider-signature surface."""
ROUTE_METHODS = {
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
DENIED_KEYS = frozenset((name, method) for name, methods in ROUTE_METHODS.items() for method in methods)


def definitions():
    return tuple((name, methods, frozenset(), "global", False, False) for name, methods in ROUTE_METHODS.items())
