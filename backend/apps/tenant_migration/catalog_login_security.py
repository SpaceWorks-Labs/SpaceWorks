"""Release-2 lane S0 (login security): tenant-dump field snapshot, projection and authority.

Every accounts login-security model DROPS from a tenant dump (data_export
`classification_login_security` gives each reason): passkeys, ceremonies, devices,
networks, alerts and the staff grace belong to one account on one deployment, and IP
rules and automatic blocks are platform-wide. Moving a space's people with their
credentials is #137 Q-B1's separate work.

`MakerspaceSecurityPolicy` is PROJECTED: the space's own security configuration travels
with it and its values are preserved -- every one of them can only make sign-in stricter
than the target's platform defaults, and the target's superadmin locks (which never
travel) still apply on top.
"""

FIELD_NAMES = {
    "accounts.WebAuthnCredential": frozenset(
        "id user credential_id public_key sign_count transports aaguid backed_up rp_id name created_at "
        "last_used_at".split()),
    "accounts.WebAuthnCeremony": frozenset(
        "id purpose user challenge rp_id origin mfa_challenge created_at expires_at consumed_at".split()),
    "accounts.StaffMfaGrace": frozenset("id user started_at source ends_at".split()),
    "accounts.KnownDevice": frozenset("id user device_hmac ua_label created_at last_verified_at revoked_at".split()),
    "accounts.KnownNetwork": frozenset("id user granularity prefix_hmac created_at last_seen".split()),
    "accounts.SecurityAlert": frozenset(
        "id user kind nonce_digest network_label ua_label sent_at expires_at used_at".split()),
    "accounts.IPAccessRule": frozenset("id cidr action note expires_at created_by created_at".split()),
    "accounts.IPAutoBlock": frozenset("id ip_key network blocked_until created_at".split()),
    "makerspaces.MakerspaceSecurityPolicy": frozenset("id makerspace values updated_at".split()),
}
EXTRA_FIELDS = {
    "accounts.PlatformLoginMethods": frozenset({"passkeys_enabled"}),
}
PROJECTED_LABELS = frozenset({"makerspaces.MakerspaceSecurityPolicy"})


def authority_entries(authority, disposition):
    return (
        (("makerspaces.MakerspaceSecurityPolicy", "values"), authority(
            disposition.PRESERVE,
            "Space security settings only tighten the target's platform defaults; target locks still apply.",
        )),
    )
