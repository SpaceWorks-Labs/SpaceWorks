"""Audit presentation for IP blocking, CAPTCHA and breached passwords (release 2, lane S-C).

``auth.*`` is the reviewed auth namespace, so those entries permit no metadata (their
``ip_key`` HMAC stays denied); the labels come from
``accounts.login_security_contract.AUDIT_ACTIONS``. ``/control/`` rule edits show only the
rule's action and which fields changed, never an address.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("auth.ip_auto_blocked", gettext_lazy("Address blocked automatically")),
    P("auth.ip_unblocked", gettext_lazy("Address unblocked")),
    P("auth.captcha_failed", gettext_lazy("CAPTCHA failed")),
    P("auth.password_breach_rejected", gettext_lazy("Breached password refused")),
    P("platform.ip_rule_saved", gettext_lazy("Platform IP rule saved"), ("action", "changed_fields", "created", "via")),
    P("platform.ip_rule_deleted", gettext_lazy("Platform IP rule deleted"), ("action", "via")),
)
