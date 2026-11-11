# Upgrade to SpaceWorks 0.11.0

> **Superseded.** The 0.11.0 candidate was never published; its changes ship in 0.12.0. This upgrade guide is kept as history — use the [0.12.0 upgrade guide](upgrade-to-0.12.0.md).

This guide accompanies the 0.11.0 release candidate. Use a published immutable release tag when it becomes available; a dev branch or an unpublished candidate is not an installable release identifier.

## Before updating

1. Record the installed immutable tag, image digests and hosting topology. Pause the automatic deploy runner and other writers or schedulers for the maintenance window. Keep the previous images available.
2. Verify a current database and object-storage backup, deployment configuration, active database identity and encryption-key custody. The updater's pre-update SQL dump does not include uploaded objects. See [backups](self-hosting.md#backups) and [database recovery](update-recovery.md).
3. If the installation still uses the retired all-in-one image, follow [moving off a single-box install](update-recovery.md#moving-off-a-single-box-install) before the update. Published deployments use the standard `spaceworks-backend` and `spaceworks-frontend` images.
4. If the database predates the fixed-role conversion, complete the [fixed-role preview and stopped-writer upgrade](update-recovery.md#fixed-role-upgrade-2026-10-16). Review obsolete notification recipient roles and Machine Manager type assignments. Account/role conversions marked irreversible require a verified backup first.

## Apply the published release

Use **Update to the latest release** in the installer, or run the installed updater with the exact published immutable suffix:

```bash
bash scripts/update.sh --version 0.11.0-main.<run>.<sha>
```

Replace the placeholders with the actual published tag. Keep the documented cloud or Helm procedure for that deployment shape. The standard wrapper preserves fork overrides while migrating the upstream repository and default images from SpaceWorks-HQ to SpaceWorks-Labs.

The updater backs up the active database, stops local application writers, runs migrations and checks readiness before reopening. Inspect failed run-once services before retrying. Do not treat a backend restart or a source build as a verified published-image update.

## Review changed behavior and settings

- The makerspace root is an overview. Inventory is now `/inventory`, prefixed `/m/<slug>` on a shared deployment. Existing item-detail and checkout routes remain. A saved **Primary homepage shortcut** orders enabled-area links and does not replace the overview or expose an unavailable area. Published custom-home content is retained.
- Existing public logo and banner settings are reused. The banner appears on the directory card and at the top of the makerspace home. An uploaded logo replaces the default public tenant-header symbol and name; directory names remain. Without uploaded artwork the existing fallbacks apply.
- SpaceWorks starts in light mode unless the visitor has saved a theme choice.
- The additive public-stats configuration migration preserves the existing display by default. Authorized area managers can change their own widget visibility under existing grants and locks. Existing publication, module, borrower-name and small-number privacy rules remain.
- The separate account-owned borrowing history does not require membership; lending must still be enabled and borrowing-account eligibility applies. Payment history and offline settlement remain core. The `payments` module controls the removable online rail.
- Shop's return window is measured from payment. Disabling inventory-consumable linking freezes new linked-stock and dependent-bundle sales while preserving original stock accounting for existing paid orders, holds and returns.
- Event ID cards and ticket designs have independent entry points and switches. Certificate design being off does not hide another enabled credential tool; the existing edit permissions still apply.
- QR revocation takes a fresh scoped row lock and records the mutation and audit together for API and direct/admin callers. No new operator switch or migration is required for this transaction correction.
- Turning off asset-unit generation prevents new units and per-unit QR identities while retaining authorized servicing/returns for existing units. Core inventory remains the quantity owner.
- The shipped Classic and Community card templates give identifiers a full-width row. Unpublished fallback cards use the updated layout when rendered. Published layouts keep their existing version; use the designer to widen a clipped Number field or explicitly reset and publish the updated template. Existing completed print files remain unchanged, while new bulk requests use the current template revision.
- The external Check-In identity integration and archive-recipient custody workflow are retired. Member sign-in replaces Check-In. Review integrations still referring to their removed settings or endpoints.
- Deployment backup and restore remain core. The current tenant module catalogue does not offer a `backup` toggle; this does not make `apps.backup` or its compatibility code removable. Keep `backup/staff_shells.py`, `backup/main_projection.py` and `backup/main_projection_verification.py` while `User.staff_makerspace` and its `INERT_SHELL_BOUNDARIES` entry exist. Retire that seam only when the field and registered boundary are removed together; see the [compatibility invariants](INVARIANTS.md).
- The per-space superadmin-off switch is retired. The web superadmin console uses platform accounts. `/control/` is server-only by default; an opt-in proxy and its allowlist remain separate from the loopback SSH tunnel. Follow [control-plane access](self-hosting.md#reaching-the-control-plane).

## Verify before reopening

1. Check health/readiness, applied migrations and strict row-security status under the runtime login. Verify that the runtime role is neither superuser nor BYPASSRLS and owns no scoped tables.
2. Sign in as a member and staff actor with the configured second factor. Check the makerspace overview, separate Inventory and enabled module navigation.
3. Exercise an evidence upload and a complete authorized loan issue/return. Confirm stock and audit history. Check a booking and the areas used by the installation.
4. Inspect background workers or the selected free/brokerless scheduler, object storage and the configured local/provider email path. Check retained balances and offline receipts before enabling online payment credentials.
5. Check public-stat visibility and manager locks, own histories, existing Shop orders, images and the selected theme.
6. Check a QR revocation and its audit record, card verification, and any printed output used by the installation. A software PDF preview is separate from checking the actual printer and duplex alignment.

If an update fails, preserve logs and the previous artifact. An application-image rollback does not undo forward database migrations. Use the [database recovery procedure](update-recovery.md) for the verified backup and matching object state. Local old-version-to-candidate migration rehearsals are pre-publication evidence; pulling and updating from the exact newly published tag can only be verified after publication.

Candidate status: complete backend/runtime regression, final QR rollback validation, deployment and old-version upgrade acceptance are still pending. Do not read this procedure as a record that those checks have already passed. Physical CR80/A4 printer acceptance has not run.
