from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.audit import services as audit
from .lifecycle_authority import require_platform_superadmin
from .lifecycle_purge_graph import _delete_object_graph
from apps.makerspaces.storage_key_collectors import (
    collect_private_object_keys as _collect_storage_keys,
    collect_public_image_keys as _collect_public_image_keys,
)


def purge(makerspace, actor):
    require_platform_superadmin(actor)
    with transaction.atomic():
        locked = makerspace.__class__.objects.select_for_update().get(pk=makerspace.pk)
        if locked.archived_at is None:
            raise ValidationError("Cannot purge a makerspace that is not archived.")
        # Capture the access decision and object locators from the locked row, never
        # the caller's potentially stale instance. Completion retains these facts.
        meta = _audit_meta(locked)
        storage_keys = _collect_storage_keys(locked)
        public_image_keys = _collect_public_image_keys(locked)
        audit.record(actor, "makerspace.purge_started", makerspace=None, target=None, meta=meta)
        from .staff_retirement import retire_staff_accounts
        retire_staff_accounts(locked, actor=actor)
        # MERGE-RECON(C): move channel cleanup into lifecycle_purge_graph's
        # deletion graph after bootstrap; preserve shared sender protections.
        from apps.integrations.messaging.purge import purge_channel
        purge_channel(locked, "sms")
        purge_channel(locked, "whatsapp")
        _delete_object_graph(locked)
        # A bulk admin action can purge several tenants inside one transaction.
        # Evaluate this tenant's deferred deletion guards before the next GUC.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

    audit.record(actor, "makerspace.purged", makerspace=None, target=None, meta=meta)
    from apps.makerspaces import lifecycle as lifecycle_barrel

    lifecycle_barrel._delete_storage_keys(storage_keys)
    lifecycle_barrel._delete_public_image_keys(public_image_keys)


def _audit_meta(makerspace):
    return {
        "makerspace_id": makerspace.pk,
        "name": makerspace.name,
        "slug": makerspace.slug,
        "superadmin_access_enabled": makerspace.superadmin_access_enabled,
    }
