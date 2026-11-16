"""Passkeys from the phone apps (decision 358 B): where a native ceremony's RP ID and origin come from.

A browser ceremony takes its origin from the request's ``Origin`` header (`rp_id.py`). A
native app sends none, and a header would be client-controlled anyway, so a native ceremony
is scoped entirely server-side:

* the RP ID is the deployment's public web domain -- ``PUBLIC_APP_BASE_URL``'s host (or
  ``PLATFORM_DOMAIN_SUFFIX`` under managed hosting), exactly the domain the
  apple-app-site-association ``webcredentials`` and the assetlinks ``get_login_creds``
  entries bind the approved apps to;
* the expected client origin is derived from the ATTESTED app identity (a device grant or an
  attestation challenge): iOS reports ``https://<rp id>``; Android reports
  ``android:apk-key-hash:<base64url SHA-256 of the signing certificate>``, and every active
  signer on the approved registration is accepted (key rotation, decision 361);
* a device MFA challenge (the second factor of a native password sign-in) is scoped the same
  way, from the attestation challenge or grant recorded in its context.

Verification itself is the web code path (`ceremonies.py`); nothing here re-implements it.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

from apps.accounts.passkeys.ceremonies import b64url
from apps.accounts.passkeys.rp_id import (
    RpIdUnavailable, normalize_origin, request_origin_and_rp_id, rp_id_for_host, validate_rp_id,
)

ANDROID_ORIGIN_PREFIX = "android:apk-key-hash:"
# Stored as an Android ceremony's origin: the registration whose active signers it accepts.
ANDROID_CEREMONY_PREFIX = "android-registration:"


def native_rp_id():
    """The RP ID every native ceremony uses; never derived from the request."""
    origin = normalize_origin(settings.PUBLIC_APP_BASE_URL)
    if not origin:
        raise RpIdUnavailable()
    return validate_rp_id(rp_id_for_host(urlsplit(origin).hostname))


def android_origin(digest_hex):
    """``android:apk-key-hash:<base64url SHA-256>`` for one signing-certificate digest."""
    try:
        digest = bytes.fromhex(str(digest_hex or "").replace(":", ""))
    except ValueError:
        digest = b""
    if len(digest) != 32:
        raise RpIdUnavailable()
    return ANDROID_ORIGIN_PREFIX + b64url(digest)


def android_registration_origins(registration_id):
    """Every origin the APPROVED Android registration's signers report (decision 361 item 3).

    Rotation-safe: an app re-signed with a newly added certificate is accepted at once, and a
    signer removed from the registration stops being accepted, whichever one a grant pinned.
    """
    from apps.accounts.models_devices import NativeAppRegistration
    from apps.accounts.native_app_identity import registration_is_eligible, registration_signing_identities
    from django.core.exceptions import ValidationError
    row = NativeAppRegistration.objects.filter(pk=registration_id, platform="android").first()
    if row is None or not registration_is_eligible(row):
        return []
    try:
        return [android_origin(digest) for digest in registration_signing_identities(row)]
    except (ValidationError, RpIdUnavailable):
        return []


def app_origin(identity, rp_id):
    """The ceremony origin stored for an attested app (grant or challenge): iOS reports
    ``https://<rp id>``; for Android the ceremony names its registration and the accepted
    origins are resolved at verification (`expected_origins`)."""
    platform = getattr(identity, "platform", None)
    if platform == "apple":
        return f"https://{rp_id}"
    if platform == "android" and android_registration_origins(identity.registration_id):
        return f"{ANDROID_CEREMONY_PREFIX}{identity.registration_id}"
    raise RpIdUnavailable()


def expected_origins(ceremony_origin):
    """What `ceremonies.verify_*` accepts for a ceremony: its own origin, or for an Android
    ceremony every active signer of the registration it was issued for."""
    if str(ceremony_origin).startswith(ANDROID_CEREMONY_PREFIX):
        try:
            registration_id = int(ceremony_origin[len(ANDROID_CEREMONY_PREFIX):])
        except ValueError:
            return []
        return android_registration_origins(registration_id)
    return ceremony_origin


def native_scope(identity):
    """``(origin, rp_id)`` for a ceremony of this attested app identity."""
    rp_id = native_rp_id()
    return app_origin(identity, rp_id), rp_id


def mfa_device_identity(context):
    """The attested app a device MFA challenge belongs to (its attestation challenge, else its
    grant); None for a web challenge or a settings enrolment."""
    device = (context or {}).get("device") or {}
    if not device or device.get("purpose") == "settings_enroll":
        return None
    from apps.accounts.models_devices import DeviceAttestationChallenge, DeviceGrant
    if device.get("attestation_id"):
        return DeviceAttestationChallenge.objects.filter(pk=device["attestation_id"]).first()
    if device.get("grant_id"):
        return DeviceGrant.objects.filter(pk=device["grant_id"]).first()
    return None


def mfa_ceremony_scope(context, request):
    """``(origin, rp_id)`` of a second-factor ceremony: the app's for a device challenge (no
    header is read), the browser's ``Origin`` otherwise."""
    if (context or {}).get("device"):
        identity = mfa_device_identity(context)
        if identity is None:
            raise RpIdUnavailable()
        return native_scope(identity)
    return request_origin_and_rp_id(request)


def device_passkey_factor_available(context):
    """Whether a device MFA challenge can offer the passkey factor at all (358 B / 361 item 4)."""
    try:
        identity = mfa_device_identity(context)
        return identity is not None and bool(native_scope(identity))
    except RpIdUnavailable:
        return False


def ceremony_scope(request):
    """``(origin, rp_id)``: the native scope for a device session, the browser's otherwise."""
    grant = getattr(request, "device_grant", None)
    if grant is not None:
        return native_scope(grant)
    return request_origin_and_rp_id(request)


def assert_person_session(request):
    """A person's own session: a browser (the web rule) or, since 358 B, a native device grant.

    A native session must be a full member-surface session of a person (never a platform
    account or a verification-only session); its grant authority does not matter, since a
    passkey belongs to the person, not to the grant.
    """
    if getattr(request, "device_grant", None) is None:
        from apps.accounts.passkeys.services import assert_web_person
        return assert_web_person(request)
    from apps.accounts.staff_identity import is_person
    user, token = request.user, getattr(request, "auth", None)
    if not is_person(user) or token is None or token.get("surface") != "member":
        raise PermissionDenied(gettext("Passkeys are for personal accounts."))
    return user


def session_after_change(user, request, browser_session):
    """The fresh session handed to the caller after a passkey change ended every other one.

    A browser gets ``browser_session(...)`` (refresh cookie); a phone keeps its grant (only its
    refresh families were revoked) and gets a new device token pair for it.
    """
    grant = getattr(request, "device_grant", None)
    if grant is None:
        return browser_session(user, request)
    from apps.accounts.native_event_grants import session_authority_for
    from apps.accounts.serializers_device import DeviceGrantSerializer
    from apps.accounts.serializers_payload import user_payload
    from apps.accounts.services_device_tokens import issue_device_token_pair
    access, refresh, _family = issue_device_token_pair(user, grant)
    return {"access": access, "refresh": refresh, "surface": "member",
            "device_grant": DeviceGrantSerializer(grant).data,
            "user": user_payload(user, request=request, session_authority=session_authority_for(grant))}
