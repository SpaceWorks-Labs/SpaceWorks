# Lane P DOB source provider

`models.EventAnswerDerivation` is tenant event evidence, independent of the
account Saved details vault. `manifest.MODEL_MANIFEST` and `COORDINATING_FIELDS`
are the literal G model/FK/source/lifecycle registration handoff. No migration,
shared barrel, runtime route or capability switch is installed in this package.

## Provider calls

1. F validates the live schema/visibility, rejects numeric age input and age
   gating, and produces canonical question descriptors. A/C/G resolve current
   actor eligibility and the existing/new `contracts.subjects.AnswerSubject`.
2. Before any event transaction call `preparation.prepare_derivations`, passing
   only visible age question IDs and server-computed form/canonical-answer
   SHA-256 values. For an owner saved DOB pass
   `accounts.saved_details.workflow.saved_dob_loader`. This is the only point
   that reads the vault. An explicit visible DOB answer must be passed for the
   consistent-source check; its ordinary disclosure remains F/subject-owned.
3. G enters the source boundary and atomic block, then calls
   `account_fences([owner_member_id], tenant_ids)` **before** event/domain locks.
   Every age insertion requires this shared account fence, including inline DOB
   and no-save-choice submission; put that owner in `LockedContext.account_ids`.
   The insertion asserts the real held fence and rechecks live fence state with
   a nonlocking query. An erased/closed fence refuses; an owner who has never
   used the vault may have no fence row and needs no account key provisioning.
   In that
   same ordered transaction A/C/G call `workflow.insert_prepared_locked` and
   persist the returned `{id,type,derivation_id}` descriptors as canonical answers.
   A newly created subject must supply its original creation operation UUID.
   Check the domain operation receipt before preparation; replay must not read
   the vault, provision a key or save a second intent. Account save choices use
   P's separate account intent preparation/epoch/fence path.

   The independent tenant DOB preparation does **not** retain an account-key
   epoch/version. The shared fence synchronizes insertion with account erasure
   and refuses insertion after persistent erasure. Ordinary vault-field deletion
   or change, account-key rotation or non-erasing key revocation while the fence
   stays open does not revoke an already-prepared source. Existing event sources
   likewise remain independent of vault
   deletion. A later preparation must resolve the then-current owner DOB/version.
4. After releasing transaction locks, response serializers call
   `serialization.project_owner`, `project_organizer`, or `OwnerAgeProvider`.
   A source decrypt can miss the DEK cache and reach KMS, so projection/export
   deliberately refuses to execute inside an atomic block. Organizer projection
   requires event registration-management plus tenant audit authority and an
   explicit live schema/blind-disclosure policy. It returns age only.

## Dates and freeze points

G adds `Event.event_date_revision` (default 1), incrementing only on starts-at or
timezone changes, including series regeneration. The date hook
`lifecycle.date_changed_locked` returns owner IDs for G's safe after-commit
notice outbox and bumps subject versions for ETags. It changes no workflow
state, submitted date, or queue position.

The owner reconfirms through `review_date_locked`; A/C/G call
`lock_subject_locked` at the contract's ordinary submission, first released
application decision/application close, or first role decision/posting close.
Normal decisions refuse pending review; `closing=True` freezes the current
date while preserving pending review. Later review of a locked subject uses
that frozen revision. Later rescheduling never recomputes a locked age.

Full-manager reopening first calls `prepare_reopen` outside locks to encrypt
the bounded reason, then `reopen_subject_locked` under ordered locks. Prior
ciphertext/date/revision/lock/version evidence is appended to `source_history`;
the audit contains references and versions, never DOB, computed age or free-text
reason. Only the owner can subsequently supply an edited DOB.

## G integration and acceptance requirements

- Import the model in G's dormant programme barrel and author migrations from
  actual leaves. Register the explicit-envelope source field with host resolver
  `event.makerspace_id`, source classification, no blind index. Do not use the
  automatic `ScopedPiiModelMixin`: that would decrypt/re-encrypt under locks.
- Register encrypted history DOB/reason paths with the source, backup,
  portability and tombstoned-retention machinery. Raw DOB never belongs in
  canonical JSON, receipt JSON, audit, search, templates, or persistent age cache.
- Install DB guards for same-event typed subject links, immutable subject
  identity, locked-source freeze/history append-only and the protected-data
  write fence. Python boundaries already enforce those rules for this provider.
- Add the coordinating subject review/lock/version fields from `manifest.py`.
  C's mentor/volunteer records remain role subjects without registrations.
- Compose `serialization.personal_data_export` separately from the global vault
  archive. Preserve retained evidence when owner edges are pseudonymized;
  account erase calls `workflow.erase_owner_drafts_locked` for each source-fenced
  event before the account-only key deletion phase. It deletes only unsubmitted
  draft sources without lock history; parent services own User-edge pseudonymization.
- Tenant fidelity capture uses `portability.capture_event_sources`; on ID or
  tenant remap, call `rebind_portable_envelopes` before import locks and separately
  remap the single typed subject FK/event ID through G's verified references.
  This authenticates and rebinds all current/history AAD envelopes. There are
  no global vault queries or object keys in the adapter.
- Domain draft deletion calls `delete_draft_sources_locked`. Event/tenant purge
  invokes `purge_event_sources_locked` before the three parent subject tables.
  Submitted/locked sources survive vault deletion and role withdrawal/revocation.

## Verification / unfinished

No Django/pytest or Docker run is permitted in this lane. All Python files were
syntax-compiled; the integration suite is written under
`backend/tests/events/programme/answer_derivations/`. G must run those files after
the registered model/coordinating fields/migrations exist. These tests include
all three subjects, role-only volunteer/mentor flow, owner/event splices,
preparation/readiness/hashes/deadline, date-review/closure/frozen date, encrypted
  reopen history, vault deletion independence, DB subject/unique constraints,
  real shared-account/exclusive-erasure lock exclusion without key provisioning,
  claimed-context refusal and saved-DOB prepare-then-erase refusal, and
tenant/history AAD rebinding. Full lane-integrated form, CSV/template disclosure,
account-erasure and tenant round-trip verification remains with F/A/C/G's actual
providers and lifecycle registries before enabling the feature.
