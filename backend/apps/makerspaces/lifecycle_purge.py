from django.utils.translation import gettext
from apps.integrations.notification_cutover import guarded
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.audit import services as audit
from .lifecycle_authority import require_platform_superadmin
from .lifecycle_purge_graph import _delete_object_graph
from apps.makerspaces.storage_key_collectors import (
    collect_private_object_keys as _collect_storage_keys,
    collect_public_image_keys as _collect_public_image_keys,
)


from apps.events.profile_photos.purge_scope import presentation_purge_scope


@guarded()
def purge(makerspace, actor):
    require_platform_superadmin(actor)
    with presentation_purge_scope(makerspace.pk, actor=actor), transaction.atomic():
        locked = makerspace.__class__.objects.select_for_update().get(pk=makerspace.pk)
        if locked.archived_at is None:
            raise ValidationError(gettext("Cannot purge a makerspace that is not archived."))
        # Capture the access decision and object locators from the locked row, never
        # the caller's potentially stale instance. Completion retains these facts.
        meta = _audit_meta(locked)
        storage_keys = _collect_storage_keys(locked)
        from .public_page_lifecycle import enqueue_tenant_pages
        enqueue_tenant_pages(locked)
        public_image_keys = _collect_public_image_keys(locked)
        audit.record(actor, "makerspace.purge_started", makerspace=None, target=None, meta=meta)
        # One account per person: nobody is retired. People keep their accounts; the
        # tenant's rows on BOTH membership tracks go with the graph, under the exact
        # tenant-purge GUC the staff-track delete guard admits.
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_purge_makerspace_id', %s, true)", [str(locked.pk)])
        _delete_object_graph(locked)
        # A bulk admin action can purge several tenants inside one transaction.
        # Evaluate this tenant's deferred deletion guards before the next GUC.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

    audit.record(actor, "makerspace.purged", makerspace=None, target=None, meta=meta)
    from apps.makerspaces import lifecycle as lifecycle_barrel

    transaction.on_commit(lambda: lifecycle_barrel._delete_storage_keys(storage_keys))
    transaction.on_commit(lambda: lifecycle_barrel._delete_public_image_keys(public_image_keys))


def _audit_meta(makerspace):
    return {
        "makerspace_id": makerspace.pk,
        "name": makerspace.name,
        "slug": makerspace.slug,
    }
