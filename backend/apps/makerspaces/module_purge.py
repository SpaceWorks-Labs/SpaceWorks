"""Superadmin-only per-module data purge (plan A9).

This is NOT `lifecycle.purge()`. That deletes an entire archived makerspace; this
deletes one module's rows while the makerspace stays live and every other module
keeps working.

The contract that makes it safe to offer at all:

* **Uninstall first.** A module must already be uninstalled (tombstoned) before its
  data can be purged. Uninstall is reversible and retains everything; purge is the
  separate, explicit, irreversible second step. Requiring the order means no single
  command can both hide and destroy.
* **Superadmin only**, mirroring `lifecycle.purge()`.
* **One transaction**, with immutability triggers bypassed for DELETE only, exactly
  as the makerspace purge does -- `session_replication_role='replica'` on self-host,
  the `app.allow_immutable_delete` GUC on managed Postgres where the replication role
  is forbidden. Both are `SET LOCAL`, so a crash can never leave the append-only
  guards durably disabled.
* **Object storage last.** Keys are collected before the delete and removed after the
  commit, best-effort: a failed S3 call must not roll back a completed purge.
"""

from django.utils.translation import gettext
from apps.integrations.notification_cutover import guarded

from contextlib import nullcontext

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.audit import services as audit
from apps.makerspaces.module_purge_plans import BY_KEY, NOT_SEPARABLE, PLANS
from apps.makerspaces.module_registry import BY_KEY as MODULE_BY_KEY
from apps.makerspaces.module_purge_storage import (
    _collect_private_key_sizes,
    _collect_private_keys,
    _collect_public_keys,
    _delete_private_keys,
    _delete_public_images_and_free_storage,
    _free_private_storage,
)


def purgeable_modules():
    """Plans in registry order, for `list_modules` and the console."""
    return [{"key": plan.key, "summary": plan.summary} for plan in PLANS]


from apps.events.profile_photos.purge_scope import presentation_purge_scope


@guarded()
def purge_module(makerspace, key, actor):
    """Delete one module's data for one makerspace. Returns the row counts."""
    plan = _resolve(makerspace, key, actor)

    meta = {
        "makerspace_id": makerspace.pk,
        "slug": makerspace.slug,
        "module": plan.key,
    }
    audit.record(actor, "makerspace.module_purge_started", makerspace=None, target=None, meta=meta)

    sources = presentation_purge_scope(makerspace.pk, actor=actor) if key == "membership" else nullcontext()
    from .module_purge_collectors_reimbursements import finance_key_context
    finance_keys = finance_key_context(makerspace, key)
    with sources, finance_keys, transaction.atomic():
        locked = makerspace.__class__.objects.select_for_update().get(pk=makerspace.pk)
        # Re-check under the lock: an install could have committed since `_resolve`.
        if plan.key in (locked.enabled_modules or []):
            raise ValidationError(
                gettext('{key} was re-installed; uninstall it again before purging.').format(key=plan.key)
            )
        # Unfinished reimbursement work refuses before any key collection or deletion.
        from .module_purge_collectors_reimbursements import purge_preflight
        purge_preflight(locked, plan.key)
        if plan.key in {'events', 'bookings'}:
            from .loan_context_generations import rotate
            rotate(locked, {plan.key})
        # Collect under the makerspace lock to narrow the attach/delete race. This does
        # not eliminate it under READ COMMITTED: a row another transaction commits
        # between this SELECT and the DELETE is invisible to the former and visible to
        # the latter, and attach paths take this lock only in managed mode because
        # `limits.add_storage` returns early on self-host.
        private_keys = _collect_private_keys(locked, plan)
        private_sizes = _collect_private_key_sizes(locked, plan)
        public_keys = _collect_public_keys(locked, plan)
        with connection.cursor() as cursor:
            if settings.MANAGED_POSTGRES:
                cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
            else:
                cursor.execute("SET LOCAL session_replication_role = 'replica'")
            counts = _purge(locked, plan, cursor)

    audit.record(
        actor,
        "makerspace.module_purged",
        makerspace=None,
        target=None,
        meta={**meta, "counts": counts},
    )
    # Both accounting paths run after commit and release quota only for objects the
    # bucket confirmed are gone -- a failed delete must free nothing, or the makerspace
    # stops being charged for storage it still holds.
    transaction.on_commit(lambda: _free_private_storage(
        makerspace, private_sizes, _delete_private_keys(private_keys)))
    # Storage HEADs cannot run inside the purge transaction: network failures must not
    # roll back deleted rows or hold the makerspace lock across one round trip per key.
    transaction.on_commit(lambda: _delete_public_images_and_free_storage(makerspace, public_keys))
    return counts


def _resolve(makerspace, key, actor):
    if not getattr(actor, "is_superuser", False):
        raise ValidationError(gettext("Only a superuser can purge module data."))
    plan = BY_KEY.get(key)
    if plan is None:
        reason = NOT_SEPARABLE.get(key)
        if reason:
            raise ValidationError(gettext('{key} cannot be purged on its own. {reason}').format(key=key, reason=reason))
        if key in MODULE_BY_KEY:
            raise ValidationError(gettext('{key} stores no data of its own, so there is nothing to purge.').format(key=key))
        raise ValidationError(gettext('Unknown module {key!r}.').format(key=key))
    if key in (makerspace.enabled_modules or []):
        raise ValidationError(
            gettext('{key} is still installed. Uninstall it first -- purging is a separate, irreversible step.').format(key=key)
        )
    return plan


def _purge(makerspace, plan, cursor):
    counts = {}
    # Payments are deliberately NOT deleted here, by any plan. Switching a module off and
    # then purging its rows is not a reason to destroy the financial record of money that
    # really changed hands -- a receipt must stay visible and a pending charge payable. They
    # do become generic-keyed references to a vanished subject, which is why `Payment`
    # snapshots `subject_label` at creation and `clean()` tolerates a missing subject on an
    # otherwise-unchanged row. The whole-makerspace `lifecycle.purge` still deletes them:
    # `Payment.makerspace` is PROTECT, so they cannot outlive their makerspace.
    # Blind-index rows have no FK to their source row, so nothing else deletes them.
    # They hold keyed HMACs of PII: leaving them behind is a real leak, not untidiness.
    if plan.pii_labels:
        from apps.encryption.models import PiiBlindIndex

        deleted = PiiBlindIndex.objects.filter(
            makerspace=makerspace, model_label__in=plan.pii_labels
        ).delete()[0]
        if deleted:
            counts["pii_blind_index"] = deleted
    outcome = plan.delete(makerspace, cursor)
    counts.update(outcome)
    # Derived facts follow their source module during an explicit destructive purge.
    # Automatic retention never reaches this path; preserving rollups there is the
    # historical-report guarantee. A module purge is different: retaining its derived
    # tenant data would violate the operator's explicit deletion boundary.
    from apps.operations.models import ReportMetricRollup, ReportRollupCursor

    rollups = ReportMetricRollup.objects.filter(
        makerspace=makerspace, source_module=plan.key
    ).delete()[0]
    cursors = ReportRollupCursor.objects.filter(
        makerspace=makerspace, source_module=plan.key
    ).delete()[0]
    if rollups:
        counts["report_metric_rollups"] = rollups
    if cursors:
        counts["report_rollup_cursors"] = cursors
    # Read the attribute directly. Every collector returns a ``PurgeResult``, so a
    # ``getattr`` default would only ever hide a future collector that forgot to report
    # its labels -- and the symptom of that is provenance silently outliving the rows it
    # describes, which is exactly what this deletion exists to prevent.
    deleted = _delete_external_references(makerspace, outcome.model_labels)
    if deleted:
        counts["external_tenant_references"] = deleted
    return counts


def _delete_external_references(makerspace, target_model_labels):
    if not target_model_labels:
        return 0
    # Imported unguarded: a tombstone removes an app's *surfaces*, never its models --
    # the rows and migrations must stay -- so this package is always importable.
    from apps.tenant_migration.models import ExternalTenantReference

    return ExternalTenantReference.objects.filter(
        makerspace=makerspace,
        target_model_label__in=target_model_labels,
    ).delete()[0]
