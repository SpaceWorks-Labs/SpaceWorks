# Events programme operator runbook

**Checkpoint `f1ef7736`, 2026-10-18: do not enable programme features.**
This repository contains the migrations/mounts and regenerated schema/client; neither those
artifacts nor syntax checks certify a working production programme. Close the named
[integration work](integration-status.md) and [acceptance evidence](acceptance.md) first.
Use the existing isolated runner; this documentation lane ran no Docker/Django tests.

## Migration and key preparation

**Setup blocker:** `makerspaces/setup_areas.py::features_for` selects all children of
chosen areas, including the five programme features when Events is chosen. Registry
defaults alone do not protect that installer/setup path. The owning lane must exclude
unaccepted programme features or add explicit independent opt-in and regression coverage;
until then verify stored enabled features after any setup operation and keep these off.

The authored graph is:

| Migration | Parent / cross-app prerequisite | Behaviour |
| --- | --- | --- |
| `accounts/0038_events_programme_schema` | accounts 0037 | Six Saved details models |
| `encryption/0008_events_programme_schema` | encryption 0007, accounts 0037 | Account key/fence models |
| `encryption/0009_account_programme_guards` | encryption 0008, accounts 0038 | Account ownership/ciphertext/epoch/erasure SQL guards |
| `organizations/0005_events_programme_schema` | organizations 0004, accounts 0037 | Organization leave receipt |
| `events/0037_events_programme_schema` | events 0036, accounts 0037, makerspaces 0096, organizations 0004 | Programme tables and cyclic FK completion |
| `events/0038_events_programme_backfills` | events 0037 | Existing event/registration/certificate/artwork/broadcast extensions |
| `events/0039_events_programme_guards` | events 0038, encryption 0009 | Frozen-content, ownership, snapshot, judging, print/library/composer guards |

Before upgrade, take a deployment backup with required recipient/key custody. Inspect actual
leaves and the merged sibling-lane graph; parallel follow-up migrations may be renumbered.
Apply through the normal deployment migration path. Test forward, reverse/reapply and
`makemigrations --check` in the correct isolated checkout before production. A rollback
to an older image is not a schema rollback.

Backfill refuses duplicate active/attended registrations for the same event/member and
unresolvable certificate subjects. Resolve such data deliberately; never merge identities
or manufacture consent to get through migration. Existing certificate direct event/member/
timezone derive from registration/event, serials/revisions stay intact and historical public
verification defaults off. Old QR mode remains legacy. Existing manual grant permissions
become manual entitlements without changing their original issuer/revocation attribution.
Reverse preflight refuses new subjects/scheduled broadcasts that cannot fit the old schema.

New environment variables and exact defaults are in the
[environment reference](../environment-reference.md#events-programme-and-account-saved-details).
Account Saved details has its own always-encrypted key system, independent of tenant PII.
Use its local wrapping key or AWS KMS policy/context; never substitute `SECRET_KEY` or a
tenant wrapping key. Keep current/previous local wrapping keys for the required transition
and existing ciphertext custody. Provisioning, KMS/readiness and photo/render-resource
preparation happen outside row-lock transactions; commands recheck prepared epochs/sources
under fences. Missing keys refuse, rather than silently enabling plaintext storage.

Credential encryption uses standard-base64 32-byte AES keys in a JSON string-version
keyring plus an independent standard-base64 32-byte HMAC digest key. Current version must
exist in the keyring. Retain old encryption versions while credentials need them; changing
the digest key invalidates lookup and needs coordinated credential reissue. Neither secret
is derived from Django/PII keys. Deployment backups require the exact configured credential
secrets and account wrapping-key custody; tenant artifacts exclude live credentials/vault keys.

**Deployment gap:** the programme's eleven new environment settings are read by Django but
are not explicitly forwarded in the checked-in Compose files or installer examples at this
checkpoint. A value in Compose's interpolation `.env` alone does not reach a container.
The deployment lane must wire backend, migration, worker/beat and applicable cloud processes
consistently before enabling; this guide does not claim an installer change was made.

## Private storage and asynchronous work

Use a private bucket and browser-reachable exact-origin upload endpoint/CORS. Backend and
browser endpoints may differ. Expose required upload headers/ETag; keep final keys unwritable
by clients. B's current transport signs exact-size/MIME POST below 25 MiB and uses multipart
at 25 MiB or above (16 MiB default parts, bounded batches). Server `list_parts`, immutable
verification copy, streaming hash and conditional final promotion establish accepted bytes.
Client ETags or completion claims are not proof.

Use two-second SDK connect/read timeouts and bounded retries. Configure 24-hour incomplete
multipart lifecycle as a secondary safeguard; it does not replace application cleanup.
The authored B transport requires tested POST/multipart/conditional-copy/version semantics;
`STORAGE_PRESIGN_METHOD=put` on the general store does not adapt it automatically. Limited
S3-compatible providers need an explicit compatible adapter/capability refusal and fault tests.
The separate cloud programme owns that work; full-server defaults must remain unchanged.

Install the typed `storage_pool_locked` provider for reservation, canonical expansion,
charge and cleanup release, idempotent per asset. [Budgets](media.md#budgets-and-media-validation)
include used plus reserved bytes; the managed 25 GB event pool must not also be denied by
the ordinary base entitlement. Imported usage starts at zero allowance until target-side
accounting/accepted-byte reconstruction is installed. Do not raise limits to hide that gap.

Scheduled now in beat and the beat-less runner: bounded admission maintenance, contributor
help expiry/escalation/notice recovery, scheduled broadcast recovery and account Saved details
work. Missing production providers can still make those jobs refuse. Required pending work:
asset scan/deadline/idle/retention/cleanup jobs, certificate batch/render resumption, print
cleanup and judging notices, with recovery after broker loss and reviewed retention-only
authority for frozen/MIGRATED_OUT sources. Runtime-off must not strand deletion obligations.

Monitor work claims/attempts/failure codes, overdue-ready assets, reserved/used/failed-cleanup
bytes and stale notice/render claims. Logs/audits carry IDs, hashes, versions and safe codes,
not DOB, private answers, raw credential/invite secrets, presigns or provider responses.

## Optional malware scanner

The B worker receives **Python runtime configuration**, not a new `CLAMAV_*` environment API:

```python
scan_options = {"backend": "none"}  # explicit development/off policy: records skipped
# Production adapter, once installed:
scan_options = {"backend": "clamav", "host": "clamav", "port": 3310,
                "max_scan_bytes": 2 * 1024**3}
```

Run clamd on a private reachable service, update its signature database and configure bounded
stream/file limits at least as large as allowed inputs. The client uses `VERSION` and
`INSTREAM`, records engine/database version and clean/infected/skipped state, and uses
five-second socket bounds. Explicit `none` is a recorded skip, not “clean”. Optional means
deployment choice; a configured unreachable/incomplete scanner returns 503/retry and never
publishes ready bytes. Infection quarantines. Test EICAR in an isolated test service plus
outage, oversized input and interrupted scans before accepting production configuration.

Account résumé scanning is a separate always-present core callback:
`ACCOUNT_SAVED_RESUME_SCAN_REQUIRED=True` plus `ACCOUNT_SAVED_RESUME_SCANNER` as an importable
callable accepting bytes and returning exactly `"clean"`. There is no installed production
callback in this checkpoint. It must remain independent of Events tombstoning. Blank/broken
required callback fails closed; an event ClamAV option does not wire account scanning.

## Video probe

Install `ffprobe` in the **Linux non-root worker** image and configure B's `SubmissionRuntime`
with `sandbox_command=("python", "-m", "apps.events.submissions.probe_sandbox")`. This is
an installation requirement, not a shipped environment variable or an implemented installer
step. Bare host execution or probing untrusted remote URLs is unsupported. The launcher
permits `file,pipe` only, verifies a local absolute nonsymlink file, and refuses root/non-Linux
with exit 78. Limits: CPU 15 seconds, address space 512 MiB, output file 64 KiB, 64 descriptors,
no core dumps; the parent timeout is 20 seconds and JSON output is capped at 64 KiB.
Check accepted MP4/WebM, no-video/multiple-video, overlong/oversized, timeout and missing-binary
cases. Missing sandbox is 503; malformed input is rejection. [Media limits](media.md) apply.

## Online scanner and print checks

V2 uses opaque `SWEC2.` payloads. Owner ticket QR and the printed badge share the current
registration credential/generation. Only an authenticated event `check_in` actor resolves
minimal member identity; resolve is read-only. Confirmation must carry payload, generation
and operation UUID through `credentials.resolution.confirm` to the canonical attendance
writer. **The existing scanner confirmation route still needs this integration.** Never
confirm by a bare registration ID after a v2 scan.

V2 is online only: old UUID resolver, roster download/sync, station and activity-token
paths must refuse v2/inert credentials. Test wrong event, rotation, cancellation, mode
adoption, expired key/generation and authority revocation between resolve/confirm. Print
at actual stock size and scan real QR resources, including long names, logo, consented
photo/no-photo fallback, light/dark designs and revoked old badges. Sample preview QR
must not resolve. Six stocks are A6 portrait, 4×6, 3×4, 4×3, CR80 portrait/landscape.

Certificate verification at `/api/v1/public/event-certificates/{verification_id}/verify/` and
SPA `/certificates/verify/{verificationId}` is separate from private PDF delivery. It
requires both explicit publication flags and returns event/date/valid-or-revoked only.
Private/ended event websites do not override that independent policy. Withdrawal or
unservable/module-off host denies; unknown/private/pending is uniform 404, no-store.

## Backup, retention and purge

Keep [live file expiry](media.md#retention-and-removal) separate from archive/offsite retention.
New object capture uses `backup/object_reference_retention.py`: ready bytes need exact
size/SHA-256; terminal expired assets are expected absence; elapsed-but-ready or in-flight
cleanup/promotion refuses capture until lifecycle finalization. Restore/import must preserve
absolute expiry and must not resurrect expired bytes or imported operational grants.

Tenant exports omit account vault/keys, credential secrets, invites, active claims and print/
outbox coordination. Import resets consent/publication/credential authority and source versions;
definitions/history are not permission to republish. Typed IDs and nested encrypted derivation
rebinding still need integrated round-trip proof. Deployment recovery includes global account
custody and different reset semantics; it is not equivalent to a portable tenant import.

Disabling/uninstalling retains rows/objects. Events purge uses dependency-ordered retained
metadata and collects all owned keys; it must preserve foreign profile bytes, account vault
and core money ledger. Durable multipart/version cleanup receipts and accounting reconciliation
are still pending. No irreversible purge or enablement is authorized merely by reading this guide.
