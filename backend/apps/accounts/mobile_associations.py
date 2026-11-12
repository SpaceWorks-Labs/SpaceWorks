"""Public association documents; app ownership never confers browser origin trust."""

import re

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.native_app_identity import eligible_registrations, registration_signing_identities
from apps.integrations.mobile_link_contract import (
    EXCLUDED_PREFIXES, NATIVE_AUTH_CALLBACK_PATHS, association_patterns,
)
from apps.makerspaces.hosting import canonical_host, verified_frontend_domains
from apps.makerspaces.platform import origin_to_hostname


def primary_frontend_hosts():
    origins = [settings.PUBLIC_APP_BASE_URL, *settings.PLATFORM_STAFF_ORIGINS]
    return frozenset(host.rstrip(".") for origin in origins if (host := origin_to_hostname(origin)))


def suffix_host():
    """``PLATFORM_DOMAIN_SUFFIX`` as a host (no leading dot), or "" when there is none."""
    return str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip().lower().strip(".")


def association_host_kind(raw_host):
    # Explicit primary URLs may use a local IP in self-host development. Custom
    # domains retain the existing stricter DNS-only canonicalization and trust gate.
    host = origin_to_hostname(raw_host).rstrip(".")
    if host in primary_frontend_hosts():
        return "shared"
    if host and host == suffix_host():
        # Under managed hosting the passkey RP ID is the suffix itself (`passkeys/rp_id.py`), so
        # iOS `webcredentials` must be served there too (decision 361). Same links as the
        # primary host, minus the sign-in callbacks that live on the primary host only.
        return "suffix"
    host = canonical_host(raw_host)
    if host and host in verified_frontend_domains():
        return "custom"
    return None


def association_components(host_kind):
    def glob(value):
        return re.sub(r"\{[a-z_]+\}", "*", value)

    components = []
    for prefix in EXCLUDED_PREFIXES:
        prefix = glob(prefix)
        components.extend(({"/": prefix, "exclude": True},
                           {"/": f"{prefix}/*", "exclude": True}))
    for shared, custom in association_patterns():
        value = custom if host_kind == "custom" else shared
        if value:
            components.extend(({"/": value}, {"/": f"{value}/"}))
    if host_kind == "shared":
        # Native sign-in callbacks live on the primary host only (the GitHub redirect URI).
        components.extend({"/": path} for path in NATIVE_AUTH_CALLBACK_PATHS)
    components.append({"/": "/*", "exclude": True})
    return components


def registration_association_identity(row):
    try:
        return registration_signing_identities(row)
    except ValidationError:
        return []


def assetlinks_document():
    document = []
    for row in eligible_registrations(production=True).filter(platform="android").order_by("pk"):
        identities = registration_association_identity(row)
        if identities:
            document.append({
                # get_login_creds is the Android twin of Apple's `webcredentials`: the app and the
                # site share saved sign-in credentials (Credential Manager). Decision 355.
                "relation": ["delegate_permission/common.handle_all_urls",
                             "delegate_permission/common.get_login_creds"],
                "target": {"namespace": "android_app", "package_name": row.app_id,
                           "sha256_cert_fingerprints": [
                               ":".join(digest[i:i + 2] for i in range(0, 64, 2)).upper()
                               for digest in identities
                           ]},
            })
    return document


def apple_association_document(host_kind):
    details, app_ids = [], []
    for row in eligible_registrations(production=True).filter(platform="apple").order_by("pk"):
        identities = registration_association_identity(row)
        if identities:
            app_id = f"{identities[0]}.{row.app_id}"
            app_ids.append(app_id)
            details.append({"appIDs": [app_id], "components": association_components(host_kind)})
    return {"applinks": {"apps": [], "details": details}, "webcredentials": {"apps": app_ids}}
