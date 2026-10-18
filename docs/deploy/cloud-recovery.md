# Managed recovery and custody

Three formats have distinct readers and guarantees. Provider database backups/PITR plus durable object storage
are independent inputs. The existing spaceworks-tenant-dump-v1 exporter supplies portable recovery only after
direct/session, maintenance, scratch, schema and anchor qualification; its supported reader imports that same
artifact into a fresh supervised host target. Managed destinations are unsupported. Ordinary tenant archives
are archive-and-purge custody records with no restore reader. Offsite SHA-256 read-back proves custody, not recovery.

Managed mode refuses deployment/compound archive production, in-place restore, sibling cutover and delayed slice
merge before effects. It cannot activate new B1 compound exclusion without its actual artifact. Never emulate
a host grant, mark an imported candidate normal, weaken two-recipient custody or reset activation history.

Record each exact provider/account/plan: DB backup enablement and retention/PITR window, operator access,
restore destination, object history/deletion retention, key escrow, regions and last offline drill. If the plan
has no verified backup/PITR, provider DB recovery is unavailable. Durability does not undo overwrite or deletion.
Current read projections show unknown until evidence exists.

Offline rebuild:

1. Stop every old web/worker/scheduler/job and revoke old DB credentials while identity is ambiguous.
2. Restore the provider DB to a NEW non-routable database. Keep recovery/binding facts intact; reconcile a source
   binding through a reviewed rebuild/adoption procedure, never a SQL reset.
3. Recover compatible object versions or a coordinated offline copy/inventory. Apply expiry/deletion receipts,
   including old-bucket late-write cleanup. Never revive expired evidence bytes.
4. Recover escrowed config/keys/provider credentials. Verify encrypted tenant/finance data is readable, immutable
   triggers/migrations match the exact build, and all identities agree.
5. Verify rows, references and object digests offline. Independent DB PITR plus a live unversioned bucket cannot
   reconstruct one historical instant. Prove writer/presign drain and a coordinated inventory if that guarantee
   is required. Unknown writers abort; never clear a durable pause blindly in finally.
6. Record actual recovery points, evidence and explicit operator acknowledgement before new admission/routing.
   Do not call the set consistent when bytes, keys or coordination are unverified.

This is not a completed provider drill. Integration still needs durable cross-process staging, complete capture
writer inventory/reconciliation and the managed rebuild binding consumer. Portable/consistent recovery cannot be
advertised until those gates pass on both storage classes. Each provider record needs actual backup ID/time,
new DB identity, object inventory/digests and decryption evidence. Keep credentials/signed URLs in private evidence.
Provider image rollback leaves applied migrations; database rollback is a separate qualified operation.
