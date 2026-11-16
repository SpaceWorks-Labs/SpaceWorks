"""SQL functions added by release-2 lane U-A1 (one account per person).

`accounts_guard_merge_record` keeps AccountMergeRecord append-only (accounts 0049);
`makerspaces_membership_track_guard` pins the membership track and every membership FK
to the track it may reference (makerspaces 0114).
"""

UNIFIED_ACCOUNT_FUNCTIONS = frozenset({
    "accounts_guard_merge_record",
    "makerspaces_membership_track_guard",
})
