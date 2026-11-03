"""Release-2 lane L8: tenant-dump field snapshot of the key-lifecycle and RLS models.

All four are OMITTED (data_export `classification_r2_l8` gives each reason); the blind
index gains the per-space search key version its rows were written with.
"""

FIELD_NAMES = {
    "encryption.KeyRotationJob": frozenset(
        "id makerspace kind status from_version to_version rows_done rows_skipped cursor attempts error_code "
        "retained_versions started_at updated_at completed_at".split()),
    "encryption.MakerspaceSearchKey": frozenset(
        "id makerspace version salt status created_at activated_at retired_at".split()),
    "encryption.RetiredPublishableKey": frozenset("id makerspace key retired_at valid_until".split()),
    "tenant_rls.FixedRoleScope": frozenset("id role_name makerspace created_at".split()),
}
EXTRA_FIELDS = {"encryption.PiiBlindIndex": frozenset({"space_key_version"})}
