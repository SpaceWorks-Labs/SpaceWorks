"""Global account profile (decisions 302-305): literal export classification.

`AccountProfile` and its three children are ACCOUNT-level data: they belong to the person, not to
any makerspace, so no tenant export or tenant dump carries them (a space only ever sees the
per-space directory projection, built at read time). They are omitted from the tenant dataset
registry and DROPPED by the tenant dump; they travel with the account (merge, purge) instead.

The one `accounts.User` FK (`AccountProfile.user`) is therefore an excluded edge, with this
reason, and the free-form JSON columns hold member-typed content, never user references.
"""

OMITTED_MODELS = {
    "makerspaces.AccountProfile": "Account-level profile; exported and purged with the account, never a space's data.",
    "makerspaces.AccountProject": "Child of the account-level profile; account-level, not tenant data.",
    "makerspaces.AccountTimelineEntry": "Child of the account-level profile; account-level, not tenant data.",
    "makerspaces.ProfileAchievement": "Child of the account-level profile; account-level, not tenant data.",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("makerspaces.AccountProfile", "user"): "Account-level profile; omitted from every tenant export and dump.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
# The four models are OMITTED above, so none of their JSON fields is part of an export and the JSON-reference
# guard (which demands exact equality with the exported models' JSON fields) must not list them.
NON_REFERENCE_JSON_FIELDS = frozenset()
