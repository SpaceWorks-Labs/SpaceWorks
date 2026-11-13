"""django-oauth-toolkit wiring for app connections (#196): token shapes, scopes, the validator.

The library does the protocol (authorization code + PKCE, refresh rotation with reuse
protection, client-secret hashing, revocation, OIDC when a signing key is configured);
this module only decides what SpaceWorks allows: the shared scope vocabulary, an app may
ask only for the scopes its space registered, and a retired app or space gets nothing.
"""
import secrets

from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.scopes import BaseScopes


def access_token(request=None):
    return f"swoa_{secrets.token_urlsafe(32)}"


def refresh_token(request=None):
    return f"swor_{secrets.token_urlsafe(40)}"


class SpaceWorksScopes(BaseScopes):
    def get_all_scopes(self):
        from .person_scopes import catalog
        return {row["value"]: row["description"] for row in catalog()}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        registration = getattr(application, "spaceworks_registration", None)
        return list(registration.allowed_scopes) if registration and registration.is_active else []

    def get_default_scopes(self, application=None, request=None, *args, **kwargs):
        from .person_scopes import ACCOUNT_READ
        return [ACCOUNT_READ] if ACCOUNT_READ in self.get_available_scopes(application) else []


class SpaceWorksOAuth2Validator(OAuth2Validator):
    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        registration = getattr(client, "spaceworks_registration", None)
        if registration is None or not registration.is_active:
            return False
        from apps.makerspaces.servability import servable_queryset
        if not servable_queryset().filter(pk=registration.makerspace_id).exists():
            return False
        return set(scopes) <= set(registration.allowed_scopes)
