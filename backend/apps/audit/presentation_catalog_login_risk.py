"""Audit presentation for the unusual-login check and security alerts (release 2, lane S-B).

``auth.*`` is the reviewed auth namespace, so these permit no metadata (it stays denied);
the labels come from ``accounts.login_security_contract.AUDIT_ACTIONS``. No row ever holds
an address, a code or a link.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("auth.login_risk_challenged", "Unusual sign-in checked"),
    P("auth.login_code_sent", "Login code sent"),
    P("auth.login_code_failed", "Login code rejected"),
    P("auth.risk_unverifiable", "Unusual sign-in could not be checked"),
    P("auth.device_remembered", "Device remembered"),
    P("auth.device_forgotten", "Device forgotten"),
    P("auth.security_alert_sent", "Security alert sent"),
    P("auth.not_me_used", "\"This wasn't me\" used"),
)
