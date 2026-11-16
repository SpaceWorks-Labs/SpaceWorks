"""System check: a configured origin must never yield a public-suffix RP ID.

A public suffix (``github.io``, ``co.uk``) is an error: passkeys scoped to it would be
usable by unrelated sites, so every ceremony refuses it anyway and the deployment is
misconfigured. An IP address only warns: browsers refuse passkeys there, so they are
simply unavailable on that address (a LAN self-host keeps working).
"""

from django.core.checks import Error, Warning, register

from apps.accounts.passkeys.rp_id import _is_ip, configured_rp_ids, is_public_suffix

_HINT = ("Set PUBLIC_APP_BASE_URL, PLATFORM_STAFF_ORIGINS and PLATFORM_DOMAIN_SUFFIX to a registrable "
         "domain you control (for example app.example.org).")


@register()
def passkey_rp_ids(app_configs=None, **kwargs):
    problems = []
    for rp_id in sorted(configured_rp_ids()):
        if _is_ip(rp_id):
            problems.append(Warning(f"Passkeys are unavailable on {rp_id!r}: an IP address cannot be a "
                                    "relying-party ID.", hint=_HINT, id="accounts.W010"))
        elif is_public_suffix(rp_id):
            problems.append(Error(f"Passkey relying-party ID {rp_id!r} is a public suffix.", hint=_HINT,
                                  id="accounts.E010"))
    return problems
