"""DRF authentication for credentials that act as a person (#196).

Both classes end in `admit_person`, which replays the live checks a person's own session
faces -- account state, the surface and staff-role route gates (`surface_policy`), the
MFA floor against the proof captured at creation or consent, the deployment recovery and
tenant-migration source gates -- and then narrows by the credential's scopes. The token
grants nothing the person could not do themselves at this moment.
"""
from django.utils.translation import gettext
import hmac

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, Throttled

from . import person_scopes
from .models_tokens import PAT_PREFIX, PersonalAccessToken, digest


def _throttle(key):
    """A per-credential budget per minute, independent of the person's other sessions."""
    window = int(timezone.now().timestamp() // 60)
    cache_key = f"person-credential:{key}:{window}"
    cache.add(cache_key, 0, timeout=120)
    if cache.incr(cache_key) > settings.PERSON_CREDENTIAL_RATE_PER_MINUTE:
        raise Throttled(wait=60)


def admit_person(request, user, mfa_claims, scopes, makerspace_id):
    from apps.accounts.authentication import _assert_source_gate
    from apps.accounts.mfa_policy import assert_verified
    from apps.accounts.surface_policy import PERSON_KIND, enforce_request, token_kind
    from apps.backup.recovery import assert_principal_allowed
    if token_kind(user) != PERSON_KIND or user.is_tenant_dump_stub or user.deletion_requested_at is not None:
        raise AuthenticationFailed(gettext("This account cannot use access tokens."))
    claims = {"kind": PERSON_KIND, "surface": "member", **(mfa_claims or {})}
    enforce_request(user, claims, request)
    assert_verified(user, claims)
    assert_principal_allowed(user)
    if user.self_registered_at is not None and user.email_verified_at is None:
        raise AuthenticationFailed(gettext("Verify the account email first."))
    _assert_source_gate(request)
    person_scopes.admit(request, scopes, makerspace_id)
    request.session_authority = "member"


class PersonalAccessTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer swpat_...`; any other bearer falls through to the JWT class."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer" or not parts[1].startswith(PAT_PREFIX.encode()):
            return None
        raw = parts[1].decode("ascii", "replace")
        lookup = raw[len(PAT_PREFIX):].split("_", 1)[0]
        row = PersonalAccessToken.objects.select_related("user").filter(lookup=lookup).first()
        if row is None or not hmac.compare_digest(row.token_digest, digest(raw)) or not row.active:
            raise AuthenticationFailed(gettext("Invalid or expired access token."))
        _throttle(f"pat:{row.pk}")
        admit_person(request, row.user, row.mfa_claims, row.scopes, row.makerspace_id)
        if row.last_used_at is None or (timezone.now() - row.last_used_at).total_seconds() > 60:
            PersonalAccessToken.objects.filter(pk=row.pk).update(last_used_at=timezone.now())
        request.person_credential = row
        return row.user, row

    def authenticate_header(self, request):
        return 'Bearer realm="api"'


class OAuthPersonAuthentication(BaseAuthentication):
    """An OAuth access token from an app connection, validated by django-oauth-toolkit."""

    def authenticate(self, request):
        from oauth2_provider.contrib.rest_framework import OAuth2Authentication
        from .models_tokens import OAuthConsent
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer" or not parts[1].startswith(b"swoa_"):
            return None
        result = OAuth2Authentication().authenticate(request)
        if result is None:
            raise AuthenticationFailed(gettext("Invalid or expired access token."))
        user, token = result
        registration = getattr(token.application, "spaceworks_registration", None)
        consent = OAuthConsent.objects.filter(user=user, application=token.application).first()
        if registration is None or not registration.is_active or consent is None:
            raise AuthenticationFailed(gettext("This app connection is no longer active."))
        _throttle(f"oauth:{token.pk}")
        scopes = set(token.scope.split()) & set(consent.scopes) & set(registration.allowed_scopes)
        admit_person(request, user, consent.mfa_claims, scopes, registration.makerspace_id)
        request.person_credential = token
        return user, token

    def authenticate_header(self, request):
        return 'Bearer realm="api"'


from drf_spectacular.extensions import OpenApiAuthenticationExtension  # noqa: E402

_NO_TOKENS = ("/api/v1/auth/", "/api/v1/admin/platform/")


class PersonalAccessTokenScheme(OpenApiAuthenticationExtension):
    target_class = PersonalAccessTokenAuthentication
    name = "personalAccessToken"

    def get_security_requirement(self, auto_schema):
        return None if auto_schema.path.startswith(_NO_TOKENS) else {self.name: []}

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "swpat_...",
                "description": "A personal access token: scoped, expiring, capped to the person's live "
                               "permissions. Never reaches sign-in, security or credential routes."}


class OAuthPersonScheme(OpenApiAuthenticationExtension):
    target_class = OAuthPersonAuthentication
    name = "oauth2"

    def get_security_requirement(self, auto_schema):
        return None if auto_schema.path.startswith(_NO_TOKENS) else {self.name: []}

    def get_security_definition(self, auto_schema):
        from django.conf import settings
        return settings.SPECTACULAR_SETTINGS["APPEND_COMPONENTS"]["securitySchemes"]["oauth2"]
