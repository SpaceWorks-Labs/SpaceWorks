# Lane 9a progress (branch `lane/9a`)

Lane scratch file -- drop it before merge.

## Done
- Rebased `codex/fp-9a` (d1dbcb72) onto dev b7c2ee93 as ONE commit (`feat(stations): phase 9a ...`,
  body records the rebase delta, original trailers kept).
  Conflicts resolved: data_export classification/references and tenant_migration
  unique_values (re-applied 9a entries into classification_domain / classification_platform /
  references_core / unique_values_core), tenant_dump_catalog digest comment merged.
- Migration renamed `makerspaces/0072_shared_station.py` -> `0073_shared_station.py`
  (depends on dev's 0072_enable_charge_tracking...); events 0023 and the migration test updated
  (test's from-state now dev's 0072). `makemigrations --check --dry-run`: No changes detected.
- Fixes squashed into the 9a commit: CATALOG_SCHEMA_SHA256 re-blessed (154297ac...);
  `tenant_migration/verification.py` tolerates an archive row lacking a user FK only when that
  field is a declared NULL omitted-field reconstruction (Station.created_by -> KeyError before).
- Separate commit: `scripts/dev.sh` forwards TOMBSTONED_APPS to the test container.

## Tests actually run
- tests/tombstone with the TOMBSTONED_APPS profile (pre-fix tree; fixes do not touch it): 182 passed.
- Main batch, pre-fix tree: 28 failed (27 catalog digest, 1 KeyError), 1654 passed, 2 xfailed.
- Re-run of the 11 failing files + materialization/verification files, post-fix: 68 passed, 2 xfailed.

## Mid-flight
- Final full main batch on the squashed tree: first attempt died on Docker host OOM, second cut off
  by the Docker restart (~01:00 IST). Re-running.

## Next
- If green: final report. Before merge: drop this file; renumber 0073 if another makerspaces 0073 lands first.
