"""Release-2 lane U-A1 (one account per person): literal export classification.

* `accounts.AccountMergeRecord` -- the platform's append-only decision record for each
  converted or merged account; its PII snapshot is ciphertext under a deployment or
  per-account key, so it is deployment-local and never a space's data.
* `accounts.AccountMergeIntent` -- transient two-sided merge proof (#65); never portable.

New columns on exported rows: `MakerspaceMembership.track` (community or staff) exports
with the roster, so a copy says which rows are staff roles. `User.merged_into/merged_at`
stay outside the literal global-user projection (`fields.py`): an alias is deployment-
local and U-D's tenant import re-establishes shells.
"""

OMITTED_MODELS = {
    "accounts.AccountMergeRecord": "Platform decision record of account unification; PII ciphertext, "
                                   "deployment-local, never portable.",
    "accounts.AccountMergeIntent": "Transient two-sided merge proof; never portable authority.",
}
EXTRA_FIELDS = {
    "makerspaces.MakerspaceMembership": "track",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("accounts.AccountMergeRecord", "source"): "Platform merge record; omitted with the record.",
    ("accounts.AccountMergeRecord", "target"): "Platform merge record; omitted with the record.",
    ("accounts.AccountMergeIntent", "survivor"): "Transient merge proof; omitted with the intent.",
    ("accounts.AccountMergeIntent", "source"): "Transient merge proof; omitted with the intent.",
    ("accounts.User", "merged_into"): "Merge alias is deployment-local; the tenant import re-establishes shells.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
