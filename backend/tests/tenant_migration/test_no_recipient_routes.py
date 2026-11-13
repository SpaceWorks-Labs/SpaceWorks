"""No archive recipient, custody or access-off surface survives (#110b, #111 Q7; release 2 L11)."""
import pathlib

from django.urls import URLPattern, URLResolver, get_resolver

FORBIDDEN = ("recipient", "custody", "access-off", "access_off", "sovereign", "emergency-disclosure")
# Notification recipients (who gets an alert) and the inventory chain of custody are unrelated.
ALLOWED = ("notification-recipient", "notificationrecipient", "chain-of-custody", "chain_of_custody")


def _routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route, pattern.name or ""


def test_no_route_names_an_archive_recipient_custody_or_access_off():
    offenders = []
    for route, name in _routes(get_resolver().url_patterns):
        text = f"{route} {name}".lower()
        if any(word in text for word in FORBIDDEN) and not any(word in text for word in ALLOWED):
            offenders.append((route, name))
    assert offenders == []


def test_no_backup_or_migration_error_code_survives():
    import apps.backup
    import apps.tenant_migration

    roots = [pathlib.Path(apps.backup.__file__).parent, pathlib.Path(apps.tenant_migration.__file__).parent]
    codes = ("custody_required", "access_off", "recipient_challenge")
    hits = [str(path) for root in roots for path in root.rglob("*.py")
            if "migrations" not in path.parts and any(code in path.read_text(encoding="utf-8") for code in codes)]
    assert hits == []
