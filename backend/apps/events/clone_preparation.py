"""Authorize and copy immutable resources before event clone row locks."""
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
            copies.prepare_image(event.makerspace, image, storage=public_image_storage)
            page = effective_page(event)
            copies.event_source = (event.pk, event.version, event.series_id, image.source_key)
            copies.page_source = page_identity(page)
            copies.prepared_page_id = None
            if page:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [EventPage._meta.db_table])
                    copies.prepared_page_id = cursor.fetchone()[0]
                for asset in bounded_children(page.assets.select_related("page__makerspace")):
                    if not website_assets.owns(asset.object_key, "events", event.makerspace_id, page.pk, asset=asset):
                        raise ValidationError("Image is not owned by the source page.")
                    copies.prepare_image(event.makerspace, OwnedImage(asset.object_key,
                        asset.object_key.rsplit("/", 1)[0]+"/",
                        website_assets.prefix("events", event.makerspace_id, copies.prepared_page_id),
                        website_assets.MAX_BYTES), storage=website_assets)
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

