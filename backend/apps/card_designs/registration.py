"""Runtime hooks the card engine installs at startup (query-free)."""


def register_runtime():
    from .email_delivery import register as register_email
    from .notifications import register as register_notifications
    register_email()
    register_notifications()
