"""Route classes for the unusual-login check (release 2, S-B). Classification opens no permission.

A person's remembered devices are their own web or app session's business (member-only,
like passkeys). The code resend and "this wasn't me" are anonymous, token-proved account
utilities, like ``auth-mfa-verify``.
"""

LOGIN_RISK_ROUTES = frozenset({"auth-devices", "auth-device-detail"})
LOGIN_RISK_ANONYMOUS_ROUTES = frozenset({"auth-login-code-resend", "auth-security-alerts-not-me"})
