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

This is not a completed provider drill. Private ciphertext staging now persists immutable owner/attempt,
bucket identity, size, digest, expiry and late-delete receipts in the primary database. Import chunks and
row sidecars cross containers through these locators; local plaintext is disposable attempt scratch. Lane D
source/derived trees are age-encrypted before object staging.
Managed adoption refuses unresolved host-local import/capture staging: finish or migrate it on its original
host before admission. A file path or timestamp alone is never proof of portable bytes.
Capture pauses persist through crashes and are never cleared in `finally`.
Every HTTP/task/job writer retains a physical session fence; only a new
boundary can acknowledge the resumed generation. Recovery cannot be advertised until the actual drain,
scratch, same-artifact target-import and provider checks pass on both storage classes. Each provider record needs actual backup ID/time,
new DB identity, object inventory/digests and decryption evidence. Keep credentials/signed URLs in private evidence.
Provider image rollback leaves applied migrations; database rollback is a separate qualified operation.

Before unversioned capture, configure `MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS` only after verifying the
selected storage provider's enforced maximum transfer duration. Zero refuses coordinated capture. The
drain waits the larger configured legacy presign floor and every recorded effective presign expiry,
plus the transfer horizon; a timed-out or dead writer remains unresolved. A platform operator can run
`python manage.py recover_managed_capture --owner <pause-uuid> --actor-id <platform-user-id>` through
the admitted management role. It must acquire the same deployment operation lock, wait the persisted
drain and acquire every original writer session lock before reconciliation; an active writer refuses.
Use `recover_managed_capture --describe --actor-id <platform-user-id>` first to read the persisted
owner, generation and unresolved-writer count. Describing a pause does not clear it.

Portable managed export runs as the finite `export_portable_tenant_dump` management command with
`--makerspace`, `--actor-id` and `--output`. Only that job receives maintenance/scratch credentials.
Provide two private, non-routable, operator-owned scratch databases through the version-1
`CLOUD_SCRATCH_DATABASES_FILE`, each with the documented `spaceworks_scratch_identity` marker and no
runtime CONNECT privilege. Their database names must be distinct and their PostgreSQL majors must match
the source; two projects both using the default name `postgres` refuse before source freeze. Qualification
precedes source freeze. The allocator holds physical exclusion,
resets only the qualified public scratch schema, and never drops either database. A crash that leaves
nonempty scratch requires explicit operator investigation and fresh qualification. Source capture selects
only registered application tables/sequences; the exact build's migrations reconstruct their schema and
application functions in scratch. Provider schemas/functions do not enter the captured image.

For an empty-bucket replacement use `migrate_cloud_storage`, install the verified replacement descriptor
while its durable pause remains held, then `resume_cloud_storage`. Nonempty buckets and live application
object references refuse this operation; physical absence alone cannot prove a safe binding change.
Do not delete/rebind history rows. Permanent evidence and staging deletion receipts retain old identity
and encrypted retired-credential custody. Ordinary archive custody remains separate from these recovery paths.

An uncertain free notification delivery needs independent provider evidence before replay. When its outcome
cannot be established, an operator may choose terminal cancellation without replay or allowance release:
run `cancel_cloud_delivery --operator-id <id> --describe <personal|channel|legacy> --id <delivery-id>`,
review the exact attempt/content/configuration fingerprints, and save the reviewed JSON with decision
`cancel_unknown_without_replay_or_release` in a protected evidence file. Execute the same command with
`--operator-id <id> --evidence-file <file>`. It rechecks the binding under task exclusion and a proved writer
drain; it never claims the provider accepted or rejected the message. Mail reservations remain charged and
need their separate `reconcile_cloud_email` provider-evidence procedure. Once every underlying claim has
been settled or explicitly cancelled, `reconcile_cloud_outbox --operator-id <id> --attempt-token <uuid>
--evidence-sha256 <digest>` can reopen that exact uncertain task. No command reclaims an unknown effect
because it is old.
