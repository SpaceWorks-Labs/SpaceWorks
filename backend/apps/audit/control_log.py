"""Every `/control/` add, change and delete writes an audit row (R4 audit B, PRD section 11).

Django admin records its own edits only in `LogEntry`, which is neither append-only nor
attested and which the audit log, its exports and the live stream never see. Only a few
admins wrote `audit.record` themselves (`config.admin_audit.AuditedControlChangeMixin` and
the admin actions), so a superadmin changing a user's role, staff flag or access status
through a `/control/` form left no audit entry at all.

Every single-object admin save and delete goes through `ModelAdmin.log_addition`,
`log_change` or `log_deletion`, which save one `LogEntry`; its `post_save` is the one hook
that sees them all. Bulk "delete selected" writes its `LogEntry` rows with `bulk_create`
(no signal), so the site-wide action is wrapped instead.

The metadata names the model and the changed FIELDS only, never values or the object's
display string: several admins hold write-only secret inputs, and a user's display string
is personal data. A deletion is recorded without a makerspace, because the space itself
may be what is being deleted.
"""

import functools
import json

from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit import services as audit


def changed_fields(message):
    try:
        parts = json.loads(message or "[]")
    except (TypeError, ValueError):
        return []
    fields = set()
    for part in parts if isinstance(parts, list) else ():
        body = part.get("changed") if isinstance(part, dict) else None
        if isinstance(body, dict):
            fields.update(str(name) for name in body.get("fields") or ())
    return sorted(fields)


def _space_of(obj):
    from apps.makerspaces.models import Makerspace

    if isinstance(obj, Makerspace):
        return obj
    return getattr(obj, "makerspace", None) if getattr(obj, "makerspace_id", None) else None


@receiver(post_save, sender=LogEntry, dispatch_uid="audit.control_log_entry")
def audit_control_log_entry(sender, instance, created, raw, **kwargs):
    if not created or raw:
        return
    try:
        obj = instance.get_edited_object()
    except Exception:  # The row is already gone or its model was removed: keep the label only.
        obj = None
    label = instance.content_type.model_class()._meta.label_lower if instance.content_type_id else ""
    user = instance.user
    if instance.action_flag == ADDITION:
        audit.record(user, "control.object_added", makerspace=_space_of(obj), target=obj, target_type=label,
                     meta={"via": "control", "model": label})
    elif instance.action_flag == CHANGE:
        audit.record(user, "control.object_changed", makerspace=_space_of(obj), target=obj, target_type=label,
                     meta={"via": "control", "model": label,
                           "changed_fields": changed_fields(instance.change_message)})
    elif instance.action_flag == DELETION:
        audit.record(user, "control.object_deleted", target=obj, target_type=label,
                     meta={"via": "control", "model": label})


def _audited(action):
    @functools.wraps(action)
    def delete_selected(modeladmin, request, queryset):
        label = modeladmin.model._meta.label_lower
        count = queryset.count()
        response = action(modeladmin, request, queryset)
        if response is None and request.POST.get("post"):  # Confirmed and deleted.
            audit.record(request.user, "control.objects_deleted", target_type=label,
                         meta={"via": "control", "model": label, "count": count})
        return response

    delete_selected.control_audited = True
    return delete_selected


def install():
    """Wrap the site-wide bulk delete once (called from AuditConfig.ready)."""
    site = admin.site
    current = site._actions.get("delete_selected")
    if current is None or getattr(current, "control_audited", False):
        return
    wrapped = _audited(current)
    site._actions["delete_selected"] = wrapped
    site._global_actions["delete_selected"] = wrapped
