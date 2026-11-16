"""Export decisions for platform security locks and superadmin PII windows.

Both are deployment-local platform authority, never tenant data: a lock is a floor set by
THIS deployment's superadmin and a PII window is an access record of THIS deployment's
superadmin. Neither travels in a tenant export or a portable archive; the audit rows that
record them do. Their user edges are excluded for the same reason.
"""

OMITTED_MODELS = {
    "makerspaces.MakerspaceSecurityLock": "Platform-set floor on a space's security settings; deployment-local "
                                          "authority, re-set by the target deployment's superadmin.",
    "accounts.PlatformPiiAccessGrant": "A superadmin's time-boxed PII access record; deployment-local, kept in "
                                       "the audit history, never portable.",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("makerspaces.MakerspaceSecurityLock", "locked_by"): "Platform superadmin attribution; omitted with the lock.",
    ("accounts.PlatformPiiAccessGrant", "actor"): "Platform superadmin attribution; omitted with the window.",
    ("accounts.PlatformPiiAccessGrant", "subject"): "Per-person window target; omitted with the window.",
}
USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
