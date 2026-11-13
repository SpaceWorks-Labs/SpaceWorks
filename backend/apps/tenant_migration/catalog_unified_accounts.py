"""Release-2 lane U-A1 (one account per person): tenant-dump field snapshot and authority.

Both new models are DROPPED (data_export `classification_unified_accounts` gives the
reason). New columns:

* `MakerspaceMembership.track` -- staff-track rows ARE the tenant's staff authority, so
  the track travels exactly like `role`: preserved for tenant staff, reset to community
  for foreign provenance. U-D's importer applies it.
* `User.merged_into/merged_at` -- a merge alias is deployment-local; shells travel as
  inert provenance and the target import re-establishes the alias (U-D).
"""

FIELD_NAMES = {
    "accounts.AccountMergeRecord": frozenset(
        "id decision source target proof_method run_id plan_sha256 snapshot_scheme snapshot_key_version "
        "snapshot_ciphertext held_fields roles_kept counts state created_at completed_at".split()),
    "accounts.AccountMergeIntent": frozenset(
        "id survivor source method identifier_digest survivor_code_digest source_code_digest "
        "survivor_code_verified_at source_code_verified_at sent_at attempts resends proved_at "
        "preview_sha256 state expires_at consumed_at cancelled_at created_at".split()),
}
EXTRA_FIELDS = {
    "accounts.User": frozenset({"merged_into", "merged_at"}),
    "makerspaces.MakerspaceMembership": frozenset({"track"}),
}


def authority_entries(authority, disposition):
    return (
        (("makerspaces.MakerspaceMembership", "track"), authority(
            (disposition.PRESERVE, disposition.RESET),
            "Staff-track rows are tenant staff authority; foreign provenance resets to community.",
        )),
        *((("accounts.User", field), authority(
            disposition.RESET, "Merge aliases are deployment-local; the target import re-establishes shells.",
        )) for field in ("merged_into", "merged_at")),
    )

# The track is read by RBAC (staff authority = staff-track rows), so it is a declared
# authorization input for the portable-import drift guard (`authority_guards`).
AUTHORITY_DECLARATIONS = {
    ("makerspaces.MakerspaceMembership", "track"): (
        "Staff-track rows are tenant staff authority; the import preserves tenant staff tracks and "
        "resets foreign provenance to community."
    ),
}
