# Lane 9a progress (branch `lane/9a`)

Lane scratch file -- drop it before merge.

## Done
- Rebased `codex/fp-9a` (d1dbcb72) onto dev b7c2ee93 as one commit.
  Conflicts resolved: data_export classification/references and tenant_migration
  unique_values (re-applied 9a entries into the split submodules), tenant_dump_catalog
  hash comment (merged; hash still to re-bless).
- Migration renamed `makerspaces/0072_shared_station.py` -> `0073_shared_station.py`
  (depends on dev's 0072_enable_charge_tracking...); events 0023 and the migration
  test updated. `makemigrations --check --dry-run`: No changes detected.
- Separate commit: `scripts/dev.sh` forwards TOMBSTONED_APPS to the test container.
- tests/tombstone (with TOMBSTONED_APPS profile): 182 passed.

## Mid-flight
- Main batch (events, module purge/lifecycle/registry, data_export, tenant_migration,
  backup events roundtrip, separability) running.

## Next
- Fix failures (expect CATALOG_SCHEMA_SHA256 re-bless), squash fixes into the 9a commit.
