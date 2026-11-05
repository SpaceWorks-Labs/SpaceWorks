"""django-oauth-toolkit settings for app connections (#196), read while settings are built.

No library import here: the generator, validator and scope classes are dotted paths that
django-oauth-toolkit imports once the app registry is ready (apps/apiclients/oauth_provider.py).
"""


def provider_settings(env):
    key = env("OAUTH_OIDC_RSA_PRIVATE_KEY", default="").replace("\\n", "\n")
    return {
        "PKCE_REQUIRED": True,
        "ROTATE_REFRESH_TOKEN": True,
        "REFRESH_TOKEN_REUSE_PROTECTION": True,
        "ACCESS_TOKEN_EXPIRE_SECONDS": env.int("OAUTH_ACCESS_TOKEN_SECONDS", default=3600),
        "REFRESH_TOKEN_EXPIRE_SECONDS": env.int("OAUTH_REFRESH_TOKEN_SECONDS", default=30 * 86400),
        "AUTHORIZATION_CODE_EXPIRE_SECONDS": 60,
        "ACCESS_TOKEN_GENERATOR": "apps.apiclients.oauth_provider.access_token",
        "REFRESH_TOKEN_GENERATOR": "apps.apiclients.oauth_provider.refresh_token",
        "OAUTH2_VALIDATOR_CLASS": "apps.apiclients.oauth_provider.SpaceWorksOAuth2Validator",
        "SCOPES_BACKEND_CLASS": "apps.apiclients.oauth_provider.SpaceWorksScopes",
        "DEFAULT_SCOPES": ["account:read"],
        "REQUEST_APPROVAL_PROMPT": "force",
        "ALLOWED_REDIRECT_URI_SCHEMES": ["https", "http"] if env.bool("DEBUG", default=False) else ["https"],
        "OIDC_ENABLED": bool(key),
        "OIDC_RSA_PRIVATE_KEY": key,
    }


PERSON_AUTHENTICATION = (
    "apps.apiclients.person_auth.PersonalAccessTokenAuthentication",
    "apps.apiclients.person_auth.OAuthPersonAuthentication",
)


def apply(rest_framework, spectacular, env):
    # First, so their `swpat_` / `swoa_` bearers are never offered to the JWT decoder.
    rest_framework["DEFAULT_AUTHENTICATION_CLASSES"] = (
        *PERSON_AUTHENTICATION, *rest_framework["DEFAULT_AUTHENTICATION_CLASSES"])
    rest_framework["DEFAULT_THROTTLE_RATES"].update({
        "person_token_manage": env("THROTTLE_PERSON_TOKEN_MANAGE", default="30/hour"),
        "oauth_consent": env("THROTTLE_OAUTH_CONSENT", default="30/hour"),
    })
    spectacular["APPEND_COMPONENTS"]["securitySchemes"]["oauth2"] = {
        "type": "oauth2",
        "description": "App connections: authorization code with PKCE (S256); refresh tokens rotate.",
        "flows": {"authorizationCode": {
            "authorizationUrl": "/api/v1/oauth/authorize/", "tokenUrl": "/api/v1/oauth/token/",
            "refreshUrl": "/api/v1/oauth/token/",
            "scopes": {"account:read": "Read my own account", "account:write": "Act on my own records",
                       "public:read": "Read the public API", "public:write": "Submit to the public API",
                       "staff:read": "Read staff routes of the app's space as my roles allow",
                       "staff:write": "Act on staff routes of the app's space as my roles allow"},
        }},
    }
    spectacular["TAGS"] = [*spectacular.get("TAGS", []),
                           {"name": "Personal access tokens", "description": "A person's own scoped, expiring tokens."},
                           {"name": "App connections", "description": "OAuth apps, consent and Connected apps."}]
