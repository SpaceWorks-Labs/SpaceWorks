"""Copy-on-write and upload bytes are prepared before event/source row locks."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4
from django.db import connection
from rest_framework.exceptions import ValidationError
from apps.events import event_authority
from apps.events.event_permissions import VIEW, EDIT_DETAILS, PUBLISH_SCHEDULE
from apps.makerspaces import website_assets
from apps.makerspaces.resource_clone import AssetCopies, OwnedImage, bounded_children
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models import EventSeries
from .models_website import EventPage
from .website_copy import owner
from .website_visibility import effective_page
from .clone_preparation import page_identity
from apps.transaction_guards import in_domain_transaction

_prepared = ContextVar("prepared_website_assets", default=None)


def current_page(target):
    return EventPage.objects.filter(series=target).first() if isinstance(target, EventSeries) else effective_page(target)


def _prepare(target, actor, copies, file):
    event_authority.require(actor, target, VIEW)
    if not (event_authority.can(actor, target, EDIT_DETAILS) or event_authority.can(actor, target, PUBLISH_SCHEDULE)):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    page = current_page(target)
    copies.page_source = page_identity(page)
    own = EventPage.objects.filter(**owner(target)).first()
    if own:
        page_id = own.pk
    else:
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [EventPage._meta.db_table])
            page_id = cursor.fetchone()[0]
    copies.prepared_page_id = page_id
    if page and own is None:
        for asset in bounded_children(page.assets.select_related("page__makerspace")):
            if not website_assets.owns(asset.object_key, "events", target.makerspace_id, page.pk, asset=asset):
                raise ValidationError("Image is not owned by the inherited page.")
            copies.prepare_image(target.makerspace, OwnedImage(asset.object_key,
                asset.object_key.rsplit("/", 1)[0]+"/", website_assets.prefix("events", target.makerspace_id, page_id),
                website_assets.MAX_BYTES), storage=website_assets)
    if file is not None:
        data = file.read(website_assets.MAX_BYTES+1)
        converted = website_assets.webp(data)
        key = website_assets.prefix("events", target.makerspace_id, page_id)+uuid4().hex+".webp"
        staged = "staging/"+key
        copies.created.extend(((website_assets, staged), (website_assets, key)))
        website_assets._put(staged, data, "application/octet-stream")
        website_assets._put(key, converted, "image/webp")
        website_assets.delete_object(staged)
        copies.prepared_upload = (key, len(converted))


def prepared_page_write(callback):
    @wraps(callback)
    def wrapped(target, *, actor, **kwargs):
        if in_domain_transaction():
            raise RuntimeError("Prepare website assets before domain transactions.")
        copies = AssetCopies()
        try:
            with boundary_tenant_write(target.makerspace_id):
                _prepare(target, actor, copies, kwargs.get("file"))
                token = _prepared.set(copies)
                try:
                    result = callback(target, actor=actor, **kwargs)
                    copies.committed = True
                    return result
                finally:
                    _prepared.reset(token)
        except BaseException:
            if not copies.committed:
                copies.cleanup()
            raise
    return wrapped


@contextmanager
def prepared_copies(target):
    copies = _prepared.get()
    if copies is None or copies.page_source != page_identity(current_page(target)):
        raise ValidationError("The website changed. Retry resource preparation.")
    yield copies
