"""Gap-api (#196) user edges: personal access tokens and app connections act as the person.

All three models are omitted in `classification_platform` because bearer authority never leaves the
deployment, so none of their account edges joins a tenant artifact's user closure.
"""

EXCLUDED_USER_EDGE_REASONS = {
    ("apiclients.PersonalAccessToken", "user"): "An omitted personal bearer credential; the person reissues it.",
    ("apiclients.OAuthConsent", "user"): "An omitted app-connection consent; the person reconnects the app.",
    ("apiclients.OAuthAppRegistration", "created_by"): "Staff attribution of an omitted, deployment-local OAuth client.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
