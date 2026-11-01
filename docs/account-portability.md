# Account portability: people, staff roles and credentials across backups and moves

Release 2, lane U-D (owner decisions #63, #65, #66, #128 C-17/C-18, #137 Q-B1, #144). This
replaces the account-split portability contract (D10/D11): there is one account per person,
staff roles are staff-track memberships on that person, and the superadmin is a separate
platform account. See [One account per person](INVARIANTS.md#one-account-per-person-release-2-lane-u-a1-63-65-66)
for the model and [SOURCE-MAP.md](SOURCE-MAP.md) for the files.

## Every row, both tracks

`MakerspaceMembership.objects` is community-only. Whole-tenant code in `backup`,
`tenant_migration`, `data_export` and `separability` therefore never reads a model it did
not name through its default manager: it uses `backup/capture_managers.every_row`, which is
the unfiltered `all_tracks` manager for memberships and the default manager everywhere else
(custom querysets keep their append-only and PII-write refusals). A guard
(`tests/backup/test_capture_manager_guard.py`) fails on a new filtered default manager that
is not declared there, on a generic `model.objects` / `_default_manager` read in those apps,
and on a reverse membership relation. Before this rule a per-space archive silently lost the
space's staff and restoring it deleted them.

## Per-space backup and restore

- **Format.** A one-space archive is `tenant_slice_v2`: the raw slice with both membership
  tracks. `tenant_slice_v1` still restores: a pre-unification roster has no `track` and each
  row takes the track the unification gave it (any built-in role but Member is a staff role).
  Any other format is refused (`archive_not_restorable`).
- **Staff after the restore point** (#144c). An active staff-track row the archive does not
  carry blocks the restore (`staff_after_restore_point`) until the superadmin revokes it. A
  v1 archive written after the unification but before staff rows were captured carries none
  and so blocks rather than deleting the space's staff.
- **Merged people** (C-17). An archived row naming a person merged since the restore point
  follows `merged_into` to the survivor; the preview lists every merge followed. A relation
  the merge registry marks UNIQUE_RESOLVE keeps the merged row on the shell when the archive
  already gives the survivor that slot, and a membership kept on a shell comes back revoked.
  A shell is never re-activated and accounts are otherwise never touched.
- **One space from a whole-platform backup** (#144b). A backup taken before the unification
  migrates through the account conversion in its scratch copy only against the operator's
  acknowledgement of that copy's own plan: `extract_space_restore_point
  --account-unification-ack <plan_sha256>` (the first refusal prints it).

## Tenant migration (PORTABLE import, format 2)

- **Staff roles travel with their person.** The roster carries both tracks; a staff-track
  row, its additional roles and machine-type scopes, and that person's notification choices
  here travel under the person's ordinary decision, with built-in roles resolved by
  protected slug to the target's seeded roles. Member personal preferences stay local.
- **Created people** keep the source status of their staff rows. **Linked people** (an
  existing target person) get every staff-track row REVOKED unless the superadmin sets
  `grant_staff_roles` on that decision, which is audited `tenant_migration.staff_roles_granted`.
  Only a person may be linked; platform provenance and shells are always created inert.
- **Shells** travel with no personal data (`users.csv` blanks them and names them
  `merged-account-<id>`). `global/user-aliases.json` names each shell's survivor when the
  survivor travels too; the import creates the shell inert and re-establishes `merged_into`,
  or retires it with no alias, both only inside that exact running import
  (`app.account_shell_import_job_id`). The import summary and its completion audit count
  shells created and re-aliased.
- **Credentials travel** (C-18, Q-B1). `global/credentials.json` holds one entry per person in
  the closure, staff and members alike: password hash, authenticator secret with recovery
  digests, and passkeys, each entry AES-GCM ciphertext under the space's active DEK bound to
  the source makerspace and user (never plaintext; a source without encryption carries no
  block and its people reset). A CREATED person with an entry arrives as a real account
  (email unverified) and signs in with them; an email already held by a target person
  refuses the import (link them instead; nothing merges on email). A LINKED person keeps the
  target's credentials. A passkey is installed only when its relying-party ID is a host of
  the target (`PUBLIC_APP_BASE_URL` or the space's verified domain). Sessions, device grants,
  refresh families, invitations and chat endpoints never travel.
- **Format 1** (the split accounts) converts on import: a staff account named by
  `staff_makerspace_id` becomes a person whose rows are staff-track rows. Other versions are
  refused.

## Sovereign tenant dump (Lane D, `spaceworks-tenant-dump-v1`)

A user travels in full when every membership is in the exiting space or when they hold an
active staff-track role there (so staff can sign in on the new server); everyone else, every
shell and every platform account becomes a PII-free member stub (a shell's alias is dropped).
Staff-track rows keep their built-in roles, additional roles and machine scopes, and the
holders' notification choices travel. A full person keeps their password hash in the sealed
dump, which only the one-shot recipients and the platform key can open; authenticator
secrets and passkeys do not travel on this path. Tenant exit keeps the one-shot `--recipient`
keys plus the platform key (#111 Q7); there is no custody.

## Data export

A space export's roster carries both tracks and its user closure includes everyone holding
a staff-track row there. A person's own (subject) export reads history recorded against any
shell merged into them (`staff_identity.actor_ids_for`) and their staff-track rows.
