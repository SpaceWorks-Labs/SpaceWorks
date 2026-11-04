"""Passkeys (WebAuthn) for people: a sign-in method and a staff second factor (#62, #74).

- ``rp_id``: the relying-party ID, only from an origin this deployment verifiably serves;
- ``ceremonies``: one-time challenges and py_webauthn verification;
- ``services``: add, rename and remove (recent re-authentication, web only);
- ``assertion``: sign-in, second factor (``verify_mfa`` for S-B), re-authentication and
  the account-merge proof hook (``begin_proof``/``verify_proof`` for U-C);
- ``policy``: whether passkeys are usable for a person (platform switch and the strictest
  ``security.passkeys_allowed`` across their staff spaces);
- ``checks``: the system check refusing a public-suffix RP ID.
"""
