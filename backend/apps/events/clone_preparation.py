"""Authorize, declare scope and copy design resources before event clone row locks.

Cover and website images are planned and journalled by ``event_asset_transaction``.
"""
from contextlib import ExitStack, contextmanager
from django.db import connection
from rest_framework.exceptions import ValidationError
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage
from apps.events.website_visibility import effective_page
from apps.makerspaces.resource_clone import AssetCopies, OwnedImage, bounded_children
from apps.makerspaces import website_assets
from apps.inventory import public_image_storage
from django.conf import settings
from apps.transaction_guards import in_domain_transaction


def page_identity(page):
    if page is None:
        return None
    return (page.pk, page.revision, tuple(page.assets.order_by("pk").values_list("pk", "object_key", "size_bytes")))


@contextmanager
def prepare(event, actor):
    if in_domain_transaction():
        raise RuntimeError("Prepare clone resources before domain transactions.")
    event = Event.objects.select_related("makerspace", "series").get(pk=event.pk)
    event_authority.require(actor, event, EDIT_DETAILS)
    event_authority.require_tenant(actor, event.makerspace)
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    copies = AssetCopies()
    try:
        with ExitStack() as stack:
            from apps.events.programme_locks import event_scopes
            from apps.encryption.preparation import prepare_tenants
            copies.tenant_ids, copies.account_ids = event_scopes(event_id=event.pk, account_ids=(actor.pk,))
            stack.enter_context(prepare_tenants(copies.tenant_ids))
            for tenant_id in copies.tenant_ids:
                stack.enter_context(boundary_tenant_write(tenant_id))
            image = cover_image(event)
            page = effective_page(event)
            copies.event_source = (event.pk, event.version, event.series_id, image.source_key)
            copies.page_source = page_identity(page)
            copies.prepared_page_id = None
            if page:
                # Pre-allocate the clone page key; the Pages reserve/replay engine plans,
                # journals and writes the cover and page images under it (decision #86).
                with connection.cursor() as cursor:
                    cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [EventPage._meta.db_table])
                    copies.prepared_page_id = cursor.fetchone()[0]
            from .certificates.clone_designs import prepare_designs
            copies.designs = prepare_designs(event, copies)
            yield copies
    except BaseException:
        if not copies.committed:
            copies.cleanup()
        raise


def cover_image(event):
    key, source_prefix = event.image_key, f"event/{event.makerspace_id}/"
    if event.series_id and "image_key" not in (event.series_override_fields or []):
        key, source_prefix = event.series.image_key, f"event-series/{event.makerspace_id}/"
    return OwnedImage(key, source_prefix, f"event/{event.makerspace_id}/", settings.PUBLIC_IMAGE_MAX_BYTES)


def revalidate(event, copies):
    from apps.events.programme_locks import event_scopes
    tenants, accounts = event_scopes(event_id=event.pk, account_ids=copies.account_ids)
    if not set(tenants) <= set(copies.tenant_ids) or not set(accounts) <= set(copies.account_ids):
        raise ValidationError("The source scope changed. Retry the copy.")
    image = cover_image(event)
    if copies.event_source != (event.pk, event.version, event.series_id, image.source_key):
        raise ValidationError("The source event changed. Retry the copy.")
    if copies.page_source != page_identity(effective_page(event)):
        raise ValidationError("The source website changed. Retry the copy.")

