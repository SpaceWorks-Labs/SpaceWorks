import re

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def check_development_attestation(app_configs=None, **kwargs):
    if settings.DEVICE_ATTESTATION_DEV_INSECURE and not settings.DEBUG:
        return [Error(
            "Development-insecure device attestation requires DEBUG=True.",
            hint="Disable DEVICE_ATTESTATION_DEV_INSECURE before production use.",
            id="accounts.E001",
        )]
    return []


@register()
def check_mobile_min_versions(app_configs=None, **kwargs):
    errors = []
    for name in ("MOBILE_MIN_VERSION_ANDROID", "MOBILE_MIN_VERSION_IOS"):
        value = getattr(settings, name)
        if value and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", value):
            errors.append(Error(
                f"{name} must be empty or a dotted numeric version.",
                hint="Use a version such as 1.4.0; no prefixes or prerelease suffixes.",
                id="accounts.E002",
            ))
    return errors
