"""Release-2 lane S0 (login security): literal export classification.

* Passkeys, ceremonies, remembered devices, familiar networks, security alerts and the
  staff grace are platform credentials, proofs and authentication telemetry of one
  account -- deployment-local, never a space's data and never portable authority.
* IP rules and automatic blocks are platform configuration and telemetry (global, #128 C-2).
* `MakerspaceSecurityPolicy` is the space's own security configuration and exports with
  the space. It has no actor column: every change is an audit row.
"""

from .types import TenantPredicate

_CREDENTIAL = "Platform credential or proof bound to one account; deployment-local, never portable authority."
_TELEMETRY = "Deployment-local authentication telemetry; never tenant data."

OMITTED_MODELS = {
    "accounts.WebAuthnCredential": _CREDENTIAL,
    "accounts.WebAuthnCeremony": "Transient passkey challenge; never portable.",
    "accounts.StaffMfaGrace": "Platform record of a person's one staff two-step grace; never tenant data.",
    "accounts.KnownDevice": _TELEMETRY,
    "accounts.KnownNetwork": _TELEMETRY,
    "accounts.SecurityAlert": "Single-use alert link digest and short-lived labels; never portable.",
    "accounts.IPAccessRule": "Platform-wide superadmin allow/deny rule; deployment configuration.",
    "accounts.IPAutoBlock": "Short-lived automatic block on a source address; deployment telemetry.",
}
EXPORTED_FIELDS = {
    "makerspaces.MakerspaceSecurityPolicy": "id makerspace values updated_at",
}
DATASET_SPECS = {
    "makerspaces.MakerspaceSecurityPolicy": ("makerspace/security_policy.csv", TenantPredicate(("makerspace",))),
}
# Registry keys mapped to booleans, integers, choice strings and CIDR text; no ids.
JSON_REFERENCE_FIELDS = frozenset({("makerspaces.MakerspaceSecurityPolicy", "values")})
EXCLUDED_USER_EDGE_REASONS = {
    ("accounts.WebAuthnCredential", "user"): "Platform credential; omitted with the passkey.",
    ("accounts.WebAuthnCeremony", "user"): "Transient challenge; omitted with the ceremony.",
    ("accounts.StaffMfaGrace", "user"): "Platform grace record; omitted with the row.",
    ("accounts.KnownDevice", "user"): "Authentication telemetry; omitted with the row.",
    ("accounts.KnownNetwork", "user"): "Authentication telemetry; omitted with the row.",
    ("accounts.SecurityAlert", "user"): "Alert link proof; omitted with the row.",
    ("accounts.IPAccessRule", "created_by"): "Platform superadmin attribution; omitted with the rule.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
