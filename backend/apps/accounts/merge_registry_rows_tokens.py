"""Account-merge dispositions for personal access tokens and app connections (#196)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_CREDENTIAL = "Credential, session or proof bound to the account; never moves."

ROWS = (
    (K, "apiclients.PersonalAccessToken", "user", _CREDENTIAL),
    (K, "apiclients.OAuthConsent", "user", _CREDENTIAL),
    (R, "apiclients.OAuthAppRegistration", "created_by", "Mutable ownership or attribution; moves to the survivor."),
    (K, "oauth2_provider.AccessToken", "user", _CREDENTIAL),
    (K, "oauth2_provider.RefreshToken", "user", _CREDENTIAL),
    (K, "oauth2_provider.Grant", "user", _CREDENTIAL),
    (K, "oauth2_provider.IDToken", "user", _CREDENTIAL),
    (K, "oauth2_provider.DeviceGrant", "user", _CREDENTIAL),
    # SpaceWorks never sets an owner on an application (OAuthAppRegistration records who registered it).
    (K, "oauth2_provider.Application", "user", "Unused by SpaceWorks; a library-owned field that stays."),
)
