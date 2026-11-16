"""Literal field snapshot for security locks and PII windows; both DROP from tenant dumps."""

FIELD_NAMES = {
    "makerspaces.MakerspaceSecurityLock": frozenset("id makerspace key floor note locked_by locked_at".split()),
    "accounts.PlatformPiiAccessGrant": frozenset(
        "id actor makerspace subject reason opened_at expires_at closed_at close_reason".split()),
}
