"""Route classes for per-space security settings and superadmin PII windows.

Classification opens no permission; each view checks Space Manager or platform-superadmin
authority itself. The names are membership-only (never delegable: owner decision #111
Q10/Q11 keeps security settings out of organization and resource grants) and reachable
by a platform account, because a superadmin edits, locks and opens PII windows here.
"""

ROUTES = frozenset({
    "admin-makerspace-security-settings",
    "admin-makerspace-security-lock",
    "admin-makerspace-pii-access",
    # Lane L8 (#120): read-only key rotation / re-key history of the space.
    "admin-makerspace-key-events",
})
