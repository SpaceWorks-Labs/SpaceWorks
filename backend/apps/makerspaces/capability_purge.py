"""Superadmin-only purge of one folded capability's data (#128 C-8, #97).

Switching a capability off keeps every row; this is the separate, irreversible step. It
follows the module-purge contract (`module_purge`) exactly, narrowed per parent:

* **Switched off first.** The stored switch must already be off -- a purge never hides
  and destroys in one step.
* **Superadmin only**, with recent re-authentication enforced by the /control/ view.
* **Preview first.** `preview` counts what would go without writing anything.
* **One transaction**, immutability triggers bypassed for DELETE only (`SET LOCAL`);
  object storage is deleted after commit, best-effort, and quota is released only for
  objects the bucket confirmed gone.
* **Audited** (`makerspace.capability_purge_started` / `makerspace.capability_purged`).
"""

from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.audit import services as audit
from apps.integrations.notification_cutover import guarded

from .capability_purge_plans import BY_KEY, PLANS
from .module_purge import (
    _delete_external_references,
    _delete_private_keys,
    _free_private_storage,
)


def purgeable_capabilities(makerspace):
    """Every plan with its switch state and preview counts, for the console."""
    stored = set(makerspace.enabled_features or [])
    return [
        {"key": plan.key, "summary": plan.summary, "switched_on": plan.key in stored,
         "counts": plan.preview(makerspace)}
        for plan in PLANS
    ]


def preview(makerspace, key):
    return _plan(key).preview(makerspace)


def _plan(key):
    plan = BY_KEY.get(key)
    if plan is None:
        raise ValidationError(gettext('{key!r} has no purgeable data of its own.').format(key=key))
    return plan


def _resolve(makerspace, key, actor):
    if not getattr(actor, "is_superuser", False):
        raise ValidationError(gettext("Only a superadmin can purge capability data."))
    plan = _plan(key)
    if key in (makerspace.enabled_features or []):
        raise ValidationError(
            gettext('{key} is still switched on. Switch it off first -- purging is a separate, irreversible step.').format(key=key)
        )
    return plan


def _collect(locked, plan):
    from apps.backup.models import RestoreRollbackObject

    keys, seen = [], set()

    def add(key):
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    if plan.private_keys is not None:
        plan.private_keys(locked, add)
    if plan.rollback_module:
        for key in RestoreRollbackObject.objects.filter(
            makerspace=locked, module_key=plan.rollback_module,
            bucket_kind=RestoreRollbackObject.BucketKind.PRIVATE,
        ).exclude(copy_key="").values_list("copy_key", flat=True):
            add(key)
    sizes = plan.private_key_sizes(locked) if plan.private_key_sizes is not None else {}
    return keys, sizes


@guarded()
def purge_capability(makerspace, key, actor):
    """Delete one capability's data for one makerspace. Returns the row counts."""
    plan = _resolve(makerspace, key, actor)
    # Recorded in the space's own log: the space survives, and its managers may read what
    # the platform deleted (the actor is the row's actor, as everywhere).
    audit.record(actor, "makerspace.capability_purge_started", makerspace=makerspace,
                 target=makerspace, meta={"capability": plan.key})
    with transaction.atomic():
        locked = makerspace.__class__.objects.select_for_update().get(pk=makerspace.pk)
        # Re-check under the lock: a switch-on could have committed since `_resolve`.
        if plan.key in (locked.enabled_features or []):
            raise ValidationError(gettext('{key} was switched back on; switch it off before purging.').format(key=plan.key))
        private_keys, private_sizes = _collect(locked, plan)
        with connection.cursor() as cursor:
            if settings.MANAGED_POSTGRES:
                cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
            else:
                cursor.execute("SET LOCAL session_replication_role = 'replica'")
            outcome = plan.delete(locked, cursor)
        counts = dict(outcome)
        external = _delete_external_references(locked, outcome.model_labels)
        if external:
            counts["external_tenant_references"] = external
    audit.record(actor, "makerspace.capability_purged", makerspace=makerspace, target=makerspace,
                 meta={"capability": plan.key, "counts": counts})
    transaction.on_commit(lambda: _free_private_storage(
        makerspace, private_sizes, _delete_private_keys(private_keys)))
    return counts
