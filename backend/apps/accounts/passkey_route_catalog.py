"""Route classes for passkeys (release 2, S-A). Classification opens no permission.

A person's own passkeys and passkey re-authentication are member-only (a person's web
session; the views refuse platform accounts and native sessions themselves). The
anonymous ceremonies -- passwordless sign-in and the second-factor options -- are shared
account utilities, like ``auth-mfa-verify``.
"""

PASSKEY_ROUTES = frozenset({
    "auth-passkeys", "auth-passkey-detail", "auth-passkeys-register-options", "auth-passkeys-register-verify",
    "auth-reauth-passkey-options", "auth-reauth-passkey",
})
PASSKEY_CEREMONY_ROUTES = frozenset({
    "auth-passkeys-authenticate-options", "auth-passkeys-authenticate-verify", "auth-mfa-passkey-options",
})
